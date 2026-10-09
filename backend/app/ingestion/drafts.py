"""Normalize raw values into a draft invoice and validate it.

The same function handles freshly extracted values and the user's corrections from the
review screen, so edits go through exactly the same checks.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.ingestion.models import REQUIRED_FIELDS
from app.ingestion.normalize import (
    clean_text,
    is_blank,
    normalize_currency_code,
    normalize_key,
    parse_amount,
    parse_date,
    parse_payment_status,
)

Severity = Literal["error", "warning", "info"]
PaymentStatus = Literal["unknown", "unpaid", "partially_paid", "paid"]
TOTAL_TOLERANCE = Decimal("1.00")  # rupee rounding on GST invoices
_LABELS = {
    "invoiceNumber": "Invoice number",
    "counterpartyName": "Customer / supplier",
    "invoiceDate": "Invoice date",
    "dueDate": "Due date",
    "currency": "Currency",
    "subtotal": "Subtotal",
    "tax": "Tax",
    "total": "Total amount",
    "paymentStatus": "Payment status",
}


@dataclass
class Issue:
    code: str
    severity: Severity
    message: str
    field: str | None = None
    suggested_value: str | None = None
    related_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "field": self.field,
            "suggestedValue": self.suggested_value,
            "relatedRecordId": self.related_record_id,
        }


@dataclass
class DraftValues:
    invoice_number: str | None = None
    counterparty_name: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    total: Decimal | None = None
    payment_status: PaymentStatus = "unknown"
    document_payment_status: str | None = None
    payment_references: list[str] = field(default_factory=list)


@dataclass
class Draft:
    values: DraftValues
    raw: dict[str, str]
    field_confidence: dict[str, float]
    confidence: float
    issues: list[Issue]
    dedupe_key: str | None

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


def build_draft(
    raw_values: dict[str, Any],
    *,
    record_type: str,
    today: date,
    field_confidence: dict[str, float] | None = None,
    payment_references: list[str] | None = None,
    user_payment_status: str | None = None,
    default_currency: str = "INR",
    date_orders: dict[str, str | None] | None = None,
) -> Draft:
    conf = dict(field_confidence or {})
    issues: list[Issue] = []
    v = DraftValues(payment_references=list(payment_references or []))
    raw = {k: _raw_str(val) for k, val in raw_values.items() if not is_blank(val)}

    v.invoice_number = clean_text(raw_values.get("invoiceNumber"), 40)
    v.counterparty_name = clean_text(raw_values.get("counterpartyName"))

    # Dates
    for key, attr in (("invoiceDate", "invoice_date"), ("dueDate", "due_date")):
        value = raw_values.get(key)
        if is_blank(value):
            continue
        parsed = parse_date(value, (date_orders or {}).get(key))
        if parsed.value is None:
            issues.append(
                Issue(
                    "unparseable_date", "error", f"Couldn't read '{raw.get(key)}' as a date.", key
                )
            )
            continue
        setattr(v, attr, parsed.value)
        if parsed.ambiguous:
            issues.append(
                Issue(
                    "ambiguous_date",
                    "warning",
                    f"Read as {parsed.value.day} {parsed.value.strftime('%b %Y')} (day/month/year). Check this is right.",
                    key,
                )
            )

    # Amounts — blank stays None; it is never treated as zero.
    for key in ("subtotal", "tax", "total"):
        value = raw_values.get(key)
        if is_blank(value):
            continue
        amount = parse_amount(value)
        if amount is None:
            issues.append(
                Issue(
                    "unparseable_amount",
                    "error",
                    f"Couldn't read '{raw.get(key)}' as an amount.",
                    key,
                )
            )
        else:
            setattr(v, key, amount)

    # Currency: never silently assumed.
    currency = normalize_currency_code(raw_values.get("currency"))
    if currency:
        v.currency = currency
        if currency != default_currency:
            issues.append(
                Issue(
                    "foreign_currency",
                    "warning",
                    f"Amounts are in {currency}. They won't be converted to ₹ and are left out of ₹ totals.",
                    "currency",
                )
            )
    else:
        v.currency = default_currency
        conf["currency"] = min(conf.get("currency", 0.5), 0.5)
        issues.append(
            Issue(
                "currency_assumed",
                "warning",
                f"No currency found; assumed {default_currency}.",
                "currency",
            )
        )

    # Payment status: what the document says is evidence, not a fact.
    doc_status = parse_payment_status(raw_values.get("paymentStatus"))
    v.document_payment_status = doc_status
    if user_payment_status in ("unpaid", "partially_paid", "paid", "unknown"):
        v.payment_status = user_payment_status  # type: ignore[assignment]
    if doc_status and v.payment_status == "unknown":
        issues.append(
            Issue(
                "payment_status_unverified",
                "info",
                f"The document says '{raw.get('paymentStatus')}'. That may be out of date, so confirm the actual payment status.",
                "paymentStatus",
                suggested_value=doc_status,
            )
        )

    issues += _validate(v, today)
    for f, c in conf.items():
        if c < 0.6 and f in raw and f in _LABELS:
            issues.append(
                Issue(
                    "low_confidence",
                    "warning",
                    f"{_LABELS[f]} was hard to read. Check it against the original.",
                    f,
                )
            )

    required_conf = [conf.get(f, 0.0) if _present(v, f) else 0.0 for f in REQUIRED_FIELDS]
    confidence = round(sum(required_conf) / len(required_conf), 3)
    return Draft(
        v,
        raw,
        conf,
        confidence,
        issues,
        dedupe_key(record_type, v.invoice_number, v.counterparty_name),
    )


def _validate(v: DraftValues, today: date) -> list[Issue]:
    issues: list[Issue] = []
    for f in REQUIRED_FIELDS:
        if not _present(v, f):
            issues.append(Issue("missing_required", "error", f"{_LABELS[f]} is missing.", f))

    if v.invoice_date and v.due_date and v.due_date < v.invoice_date:
        issues.append(
            Issue("due_before_invoice", "error", "Due date is before the invoice date.", "dueDate")
        )
    if v.invoice_date and v.invoice_date > today + timedelta(days=1):
        issues.append(
            Issue("future_date", "warning", "Invoice date is in the future.", "invoiceDate")
        )
    if v.invoice_date and v.invoice_date.year < 2000:
        issues.append(
            Issue(
                "implausible_date",
                "warning",
                "Invoice date looks too old. Check the year.",
                "invoiceDate",
            )
        )

    for key in ("subtotal", "tax", "total"):
        amount = getattr(v, key)
        if amount is not None and amount < 0:
            issues.append(
                Issue(
                    "negative_amount",
                    "warning",
                    f"{_LABELS[key]} is negative. Is this a credit note?",
                    key,
                )
            )

    if v.subtotal is not None and v.tax is not None:
        expected = v.subtotal + v.tax
        if v.total is None:
            issues.append(
                Issue(
                    "missing_required",
                    "error",
                    f"Total amount is missing. Subtotal + tax would be {_fmt(expected)}.",
                    "total",
                    suggested_value=str(expected),
                )
            )
        elif abs(expected - v.total) > TOTAL_TOLERANCE:
            issues.append(
                Issue(
                    "total_mismatch",
                    "error",
                    f"Subtotal {_fmt(v.subtotal)} + tax {_fmt(v.tax)} = {_fmt(expected)}, but the total says {_fmt(v.total)}.",
                    "total",
                    suggested_value=str(expected),
                )
            )
    elif (
        v.subtotal is not None
        and v.total is not None
        and v.tax is None
        and v.total > v.subtotal + TOTAL_TOLERANCE
    ):
        issues.append(
            Issue(
                "tax_missing",
                "warning",
                f"Total is {_fmt(v.total - v.subtotal)} more than the subtotal, but no tax was found.",
                "tax",
                suggested_value=str(v.total - v.subtotal),
            )
        )
    if v.tax is not None and v.total is not None and v.total > 0 and v.tax > v.total:
        issues.append(
            Issue("tax_exceeds_total", "error", "Tax is larger than the total amount.", "tax")
        )
    # Remove the generic "total missing" duplicate when the suggestion version exists.
    seen: set[tuple[str, str | None]] = set()
    unique = []
    for i in sorted(issues, key=lambda i: i.suggested_value is None):
        if (i.code, i.field) in seen:
            continue
        seen.add((i.code, i.field))
        unique.append(i)
    return unique


def _present(v: DraftValues, f: str) -> bool:
    attr = {
        "invoiceNumber": "invoice_number",
        "counterpartyName": "counterparty_name",
        "invoiceDate": "invoice_date",
    }.get(f, f)
    return getattr(v, attr) is not None


def _fmt(amount: Decimal) -> str:
    return f"{amount:,.2f}"


def _raw_str(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if hasattr(value, "isoformat"):
        return str(value.isoformat())[:10]
    return str(value)[:200]


def dedupe_key(
    record_type: str, invoice_number: str | None, counterparty: str | None
) -> str | None:
    """Business-scoped duplicate key; None when there's no invoice number to compare."""
    inv = normalize_key(invoice_number)
    if not inv:
        return None
    raw = f"{record_type}|{inv}|{normalize_key(counterparty)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def mark_in_file_duplicates(drafts: list[tuple[str, Draft]]) -> None:
    """Flag later rows that repeat an earlier row's invoice number + party in the same file."""
    first_seen: dict[str, str] = {}
    for row_id, draft in drafts:
        if not draft.dedupe_key:
            continue
        if draft.dedupe_key in first_seen:
            draft.issues.append(
                Issue(
                    "duplicate_in_file",
                    "warning",
                    "This invoice appears more than once in this file.",
                    "invoiceNumber",
                    related_record_id=first_seen[draft.dedupe_key],
                )
            )
        else:
            first_seen[draft.dedupe_key] = row_id
