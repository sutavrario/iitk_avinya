"""Extract invoice fields from PDF/OCR text.

`ExtractionProvider` is the seam for smarter extractors (e.g. Gemini). The built-in
`RuleBasedExtractor` is free, deterministic and good for common Indian GST invoice layouts.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.ingestion.errors import IngestionError
from app.ingestion.models import PageText, RawRecord, SourceRef
from app.ingestion.normalize import detect_currency, parse_amount

RecordType = str  # "sales_invoice" | "purchase_invoice"


class ExtractionProvider(Protocol):
    name: str

    def extract(self, pages: list[PageText], record_type: RecordType) -> list[RawRecord]: ...


# --- Patterns --------------------------------------------------------------------------------

_AMT = r"(?:₹|rs\.?|inr)?\s*\(?-?\d[\d,]*(?:\.\d{1,2})?\)?(?:\s*/-)?"
_DATE = (
    r"\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{1,2}(?:st|nd|rd|th)?[ -][A-Za-z]{3,9}[ -,]*\d{2,4}"
    r"|[A-Za-z]{3,9} \d{1,2},? \d{4}"
)
_SEP = r"\s*(?:[:\-–]|is)?\s*"
_FLAGS = re.IGNORECASE

_INVOICE_NO = re.compile(
    r"(?:tax\s+)?(?:invoice|inv|bill)\s*(?:no\.?|number|num|#)"
    + _SEP
    + r"([A-Z0-9][A-Z0-9\-/]{0,30})",
    _FLAGS,
)
_INVOICE_DATE = re.compile(
    r"(?:invoice\s*date|inv\.?\s*date|bill\s*date|date\s*of\s*issue|dated)" + _SEP + f"({_DATE})",
    _FLAGS,
)
_GENERIC_DATE = re.compile(r"(?<![a-z])date" + _SEP + f"({_DATE})", _FLAGS)
_DUE_DATE = re.compile(
    r"(?:due\s*date|due\s*on|payment\s*due|due\s*by)" + _SEP + f"({_DATE})", _FLAGS
)
_SUBTOTAL = re.compile(
    r"(?:sub\s*-?\s*total|taxable\s*(?:value|amount|amt)|amount\s*before\s*tax)"
    + _SEP
    + f"({_AMT})",
    _FLAGS,
)
_TOTAL_TAX = re.compile(
    r"(?:total\s*tax|total\s*gst|tax\s*amount|gst\s*amount)" + _SEP + f"({_AMT})", _FLAGS
)
_TAX_PART = re.compile(
    r"\b(?:cgst|sgst|igst|utgst)\b[^\n\d]*(?:@?\s*\d+(?:\.\d+)?\s*%)?" + _SEP + f"({_AMT})", _FLAGS
)
_TOTAL_SPECIFIC = re.compile(
    r"(?:grand\s*total|total\s*amount(?:\s*payable)?|invoice\s*(?:total|value|amount)|amount\s*payable|net\s*payable)"
    r"(?:\s*\([^)]*\))?" + _SEP + f"({_AMT})",
    _FLAGS,
)
_TOTAL_GENERIC = re.compile(
    r"^\s*total(?!\s*tax)(?!\s*gst)(?:\s*\([^)]*\))?" + _SEP + f"({_AMT})\\s*$",
    _FLAGS | re.MULTILINE,
)
_BALANCE_DUE = re.compile(r"balance\s*(?:due|outstanding)" + _SEP + f"({_AMT})", _FLAGS)
_STATUS = re.compile(r"(?:payment\s*status|status)" + _SEP + r"([A-Za-z ]{3,20})", _FLAGS)
_PAID_STAMP = re.compile(r"^\s*(paid|unpaid)\s*$", _FLAGS | re.MULTILINE)
_REFS = re.compile(
    r"(?:utr|txn\s*id|transaction\s*id|payment\s*ref(?:erence)?|cheque\s*no\.?|chq\s*no\.?)"
    + _SEP
    + r"([A-Z0-9][A-Z0-9\-/]{5,30})",
    _FLAGS,
)
_PARTY_LABEL_SALES = re.compile(
    r"^\s*(?:bill(?:ed)?\s*to|buyer|customer(?:\s*name)?|sold\s*to|client|consignee)\b"
    + _SEP
    + r"(.*)$",
    _FLAGS | re.MULTILINE,
)
_PARTY_LABEL_PURCHASE = re.compile(
    r"^\s*(?:from|supplier|vendor|seller|sold\s*by)\b" + _SEP + r"(.*)$", _FLAGS | re.MULTILINE
)


@dataclass
class _Found:
    value: str
    confidence: float
    snippet: str


class RuleBasedExtractor:
    name = "rules"

    def extract(self, pages: list[PageText], record_type: RecordType) -> list[RawRecord]:
        if not any(p.text.strip() for p in pages):
            raise IngestionError("no_text_found", "No readable text was found in this document.")
        groups = _group_pages(pages)
        return [r for g in groups if (r := self._extract_one(g, record_type)) is not None]

    def _extract_one(self, pages: list[PageText], record_type: RecordType) -> RawRecord | None:
        text = "\n".join(p.text for p in pages)
        base = min(p.confidence for p in pages)
        method = "ocr" if any(p.method == "ocr" for p in pages) else "text_layer"
        found: dict[str, _Found] = {}

        def take(field: str, m: re.Match[str] | None, weight: float = 0.9) -> None:
            if m and field not in found:
                found[field] = _Found(
                    m.group(1).strip(), round(weight * base, 3), m.group(0).strip()[:80]
                )

        take("invoiceNumber", _INVOICE_NO.search(text))
        if method == "ocr" and "invoiceNumber" in found:
            _repair_ocr_invoice_number(text, found)
        take("invoiceDate", _INVOICE_DATE.search(text))
        if "invoiceDate" not in found:
            for m in _GENERIC_DATE.finditer(text):
                if "due" not in text[max(0, m.start() - 8) : m.start()].lower():
                    take("invoiceDate", m, 0.7)
                    break
        take("dueDate", _DUE_DATE.search(text))
        take("subtotal", _SUBTOTAL.search(text))
        take("total", _TOTAL_SPECIFIC.search(text))
        if "total" not in found:
            generic = list(_TOTAL_GENERIC.finditer(text))
            take("total", generic[-1] if generic else None, 0.75)

        tax = _TOTAL_TAX.search(text)
        if tax:
            take("tax", tax)
        else:
            parts = [parse_amount(m.group(1)) for m in _TAX_PART.finditer(text)]
            if parts and all(p is not None for p in parts):
                total_tax = sum((p for p in parts if p is not None), Decimal("0"))
                found["tax"] = _Found(
                    str(total_tax), round(0.8 * base, 3), "sum of CGST/SGST/IGST lines"
                )

        party = _find_party(text, record_type)
        if party:
            found["counterpartyName"] = party

        status = _document_payment_status(text)
        if status:
            found["paymentStatus"] = _Found(status, round(0.8 * base, 3), status)

        if not found:
            return None
        currency = detect_currency(text)
        values: dict[str, object] = {k: v.value for k, v in found.items()}
        if currency:
            values["currency"] = currency
        refs = list(dict.fromkeys(m.group(1) for m in _REFS.finditer(text)))[:10]
        snippet = found.get("invoiceNumber", found.get("total", next(iter(found.values())))).snippet
        return RawRecord(
            values=values,
            source=SourceRef(method=method, page=pages[0].page, snippet=snippet),  # type: ignore[arg-type]
            field_confidence={k: v.confidence for k, v in found.items()},
            payment_references=refs,
        )


_OCR_INVOICE_LINE = re.compile(
    r"(?:tax\s+)?(?:invoice|inv|bill)\s*(?:no\.?|number|num|#)"
    + _SEP
    + r"([A-Z0-9][A-Z0-9\-/ ]{0,40})$",
    _FLAGS | re.MULTILINE,
)


def _repair_ocr_invoice_number(text: str, found: dict[str, _Found]) -> None:
    """OCR often splits identifiers ('BWS/9 1/2026'). Rejoin digit groups and separators on the
    same line, and lower confidence so the user is asked to check it."""
    m = _OCR_INVOICE_LINE.search(text)
    if not m:
        return
    candidate = m.group(1).strip()
    joined = re.sub(r"\s*([/\-])\s*", r"\1", candidate)
    joined = re.sub(r"(?<=\d) (?=\d)", "", joined)
    if " " in joined or joined == found["invoiceNumber"].value or len(joined) > 30:
        return
    prev = found["invoiceNumber"]
    found["invoiceNumber"] = _Found(
        joined, round(prev.confidence * 0.6, 3), m.group(0).strip()[:80]
    )


def _group_pages(pages: list[PageText]) -> list[list[PageText]]:
    """One record per page when each page carries its own invoice number; otherwise one per document."""
    numbers = [m.group(1) if (m := _INVOICE_NO.search(p.text)) else None for p in pages]
    if len(pages) > 1 and all(numbers) and len(set(numbers)) == len(pages):
        return [[p] for p in pages]
    return [pages]


def _find_party(text: str, record_type: RecordType) -> _Found | None:
    label = _PARTY_LABEL_PURCHASE if record_type == "purchase_invoice" else _PARTY_LABEL_SALES
    m = label.search(text)
    if m:
        value = m.group(1).strip()
        if not value:  # name on the next non-empty line
            rest = text[m.end() :].lstrip("\n")
            value = next((line.strip() for line in rest.splitlines() if line.strip()), "")
        value = re.split(r"\s{3,}|\t|gstin", value, flags=re.IGNORECASE)[0].strip(" :,-")
        if value:
            return _Found(value[:120], 0.85, m.group(0).strip()[:80])
    if record_type == "purchase_invoice":
        # A supplier's bill usually starts with the supplier's own name.
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first and not re.search(r"invoice|bill|receipt", first, re.IGNORECASE):
            return _Found(first[:120], 0.5, first[:80])
    return None


def _document_payment_status(text: str) -> str | None:
    m = _STATUS.search(text)
    if m:
        return m.group(1).strip()
    stamp = _PAID_STAMP.search(text)
    if stamp:
        return stamp.group(1)
    balance = _BALANCE_DUE.search(text)
    if balance:
        amount = parse_amount(balance.group(1))
        if amount is not None:
            return "paid" if amount == 0 else "balance due"
    return None


class LlmExtractionProvider:
    """Placeholder for LLM-assisted extraction (e.g. Gemini with a JSON schema).

    Contract: given page texts (and optionally page images), return RawRecords whose values
    are raw strings exactly as they appear, with per-field confidence. Output still goes
    through the same normalization and validation as every other extractor, so a model
    can never bypass the checks. Not configured yet.
    """

    name = "llm"

    def extract(self, pages: list[PageText], record_type: RecordType) -> list[RawRecord]:
        raise IngestionError("llm_unavailable", "AI-assisted extraction isn't configured yet.")


def build_extraction_provider(name: str) -> ExtractionProvider:
    if name == "llm":
        return LlmExtractionProvider()
    return RuleBasedExtractor()
