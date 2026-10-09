"""Pipeline tests on the sample files (no Firebase needed)."""

import io
import shutil
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image

from app.ingestion import spreadsheet
from app.ingestion.drafts import build_draft, dedupe_key
from app.ingestion.errors import IngestionError
from app.ingestion.normalize import infer_date_order, parse_amount, parse_date
from app.ingestion.ocr import OcrResult, TesseractOcrProvider, UnavailableOcrProvider
from app.ingestion.pipeline import ExtractionOptions, ExtractionOutcome, run_extraction
from app.ingestion.text_extractor import LlmExtractionProvider, RuleBasedExtractor

SAMPLES = Path(__file__).resolve().parents[3] / "sample_data" / "ingestion"
TODAY = date(2026, 10, 9)


class FakeOcr:
    """Deterministic OCR: returns fixed text and records calls."""

    name = "fake"

    def __init__(self, text: str = "", confidence: float = 0.92) -> None:
        self.text, self.confidence, self.calls = text, confidence, 0

    def is_available(self) -> bool:
        return True

    def recognize(self, image: Image.Image) -> OcrResult:
        self.calls += 1
        return OcrResult(self.text, self.confidence)


class ExplodingOcr(FakeOcr):
    def recognize(self, image: Image.Image) -> OcrResult:
        raise AssertionError("OCR must not run for a PDF with a text layer")


INVOICE_TEXT = """Sharma General Store
TAX INVOICE
Invoice No: SGS/2026/0457
Invoice Date: 18/09/2026
Due Date: 18/10/2026
Bill To: Deshmukh Caterers
Sub Total: Rs. 13,380.00
CGST @ 2.5%: Rs. 334.50
SGST @ 2.5%: Rs. 334.50
Grand Total: Rs. 14,049.00
Payment Status: Unpaid"""


def extract(name: str, ocr: object | None = None, **opts: object) -> ExtractionOutcome:
    path = SAMPLES / name
    return run_extraction(
        path.read_bytes(),
        extension=path.suffix.lower(),
        options=ExtractionOptions(**opts),  # type: ignore[arg-type]
        ocr=ocr or FakeOcr(),  # type: ignore[arg-type]
        extractor=RuleBasedExtractor(),
        today=TODAY,
    )


def issue_codes(row: object) -> set[str]:
    return {i.code for i in row.draft.issues}  # type: ignore[attr-defined]


# --- Normalization ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("₹1,23,456.78", Decimal("123456.78")),
        ("Rs. 500/-", Decimal("500.00")),
        ("INR 1,000", Decimal("1000.00")),
        ("(1,200.00)", Decimal("-1200.00")),
        (41100.0, Decimal("41100.00")),
        (0, Decimal("0.00")),  # an explicit zero is kept
        ("", None),
        (None, None),
        ("N/A", None),
        ("abc", None),
        ("1.2.3", None),
        ("Col1", None),
        ("INV-1001", None),
        ("2 pcs", None),
    ],
)
def test_parse_amount(raw: object, expected: Decimal | None) -> None:
    assert parse_amount(raw) == expected


def test_parse_date_formats_and_ambiguity() -> None:
    assert parse_date("2026-09-18").value == date(2026, 9, 18)
    assert parse_date("18/09/2026").value == date(2026, 9, 18)
    assert parse_date("5-Aug-2026").value == date(2026, 8, 5)
    assert parse_date("Sep 3, 2026").value == date(2026, 9, 3)
    assert parse_date(46280).value == date(2026, 9, 15)  # Excel serial
    assert parse_date("31/02/2026").value is None
    assert parse_date("03/04/2026").ambiguous
    assert not parse_date("03/04/2026", "dmy").ambiguous
    assert parse_date("03/04/2026", "mdy").value == date(2026, 3, 4)
    assert infer_date_order(["01/09/2026", "31/08/2026"]) == "dmy"
    assert infer_date_order(["09/01/2026", "08/31/2026"]) == "mdy"
    assert infer_date_order(["01/02/2026"]) is None


def test_dedupe_key_ignores_formatting_but_not_party() -> None:
    a = dedupe_key("sales_invoice", "INV-1001", "Patel Agencies")
    assert a == dedupe_key("sales_invoice", "inv 1001", "PATEL  agencies.")
    assert a != dedupe_key("sales_invoice", "INV-1001", "Gupta Kirana")
    assert a != dedupe_key("purchase_invoice", "INV-1001", "Patel Agencies")
    assert dedupe_key("sales_invoice", None, "Patel") is None


# --- Validation rules ---------------------------------------------------------------------------


def draft(**values: object):  # type: ignore[no-untyped-def]
    base = {
        "invoiceNumber": "INV-1",
        "counterpartyName": "A",
        "invoiceDate": "2026-09-01",
        "total": "118",
        "currency": "INR",
    }
    return build_draft({**base, **values}, record_type="sales_invoice", today=TODAY)


def test_missing_values_are_never_zero() -> None:
    d = draft(total=None, subtotal=None, tax=None)
    assert d.values.total is None and d.values.subtotal is None and d.values.tax is None
    assert any(i.code == "missing_required" and i.field == "total" for i in d.issues)
    assert d.has_errors


def test_total_mismatch_and_suggestion() -> None:
    d = draft(subtotal="100", tax="18", total="120")
    issue = next(i for i in d.issues if i.code == "total_mismatch")
    assert issue.severity == "error" and issue.suggested_value == "118.00"
    assert not draft(subtotal="100", tax="18", total="118.50").has_errors  # within ₹1 rounding


def test_total_missing_suggests_sum() -> None:
    d = draft(subtotal="100", tax="18", total=None)
    missing = next(i for i in d.issues if i.field == "total")
    assert missing.suggested_value == "118.00"
    assert d.values.total is None


def test_document_payment_status_is_evidence_only() -> None:
    d = draft(paymentStatus="Unpaid")
    assert d.values.payment_status == "unknown"
    assert d.values.document_payment_status == "unpaid"
    assert any(i.code == "payment_status_unverified" for i in d.issues)
    confirmed = build_draft(
        {
            "invoiceNumber": "1",
            "counterpartyName": "A",
            "invoiceDate": "2026-09-01",
            "total": "1",
            "paymentStatus": "Unpaid",
        },
        record_type="sales_invoice",
        today=TODAY,
        user_payment_status="paid",
    )
    assert confirmed.values.payment_status == "paid"
    assert not any(i.code == "payment_status_unverified" for i in confirmed.issues)


def test_currency_is_never_silently_assumed() -> None:
    d = draft(currency=None)
    assert d.values.currency == "INR"
    assert any(i.code == "currency_assumed" for i in d.issues)
    assert any(i.code == "foreign_currency" for i in draft(currency="USD").issues)


def test_date_rules() -> None:
    assert any(i.code == "due_before_invoice" for i in draft(dueDate="2026-08-01").issues)
    assert any(i.code == "future_date" for i in draft(invoiceDate="2027-01-01").issues)
    assert any(i.code == "unparseable_date" for i in draft(invoiceDate="31/02/2026").issues)


# --- Spreadsheets -------------------------------------------------------------------------------


def test_clean_register_sums_gst_columns() -> None:
    out = extract("sales_register.xlsx")
    assert out.status == "needs_review" and out.method == "spreadsheet"
    assert out.mapping["tax"] == ["CGST", "SGST"]
    assert len(out.rows) == 4
    first = out.rows[0]
    assert first.source.sheet_name == "Sales" and first.source.row_number == 2
    assert first.draft.values.tax == Decimal("7398.00")
    assert first.draft.values.total == Decimal("48498.00")
    assert not any(r.draft.has_errors for r in out.rows)
    assert out.rows[1].draft.values.payment_references == ["UTR123456789"]
    assert any(w.code == "currency_assumed" for w in out.warnings)  # once, at document level
    assert all("currency_assumed" not in issue_codes(r) for r in out.rows)


def test_tally_export_finds_header_and_skips_totals() -> None:
    out = extract("tally_sales_export.xlsx")
    assert out.sheet_name == "Sales Register"
    assert "Notes" in out.sheet_names
    assert out.header_row_number == 5
    assert [r.draft.values.invoice_number for r in out.rows] == [
        "S/245",
        "S/246",
        "S/247",
    ]  # no Grand Total row
    assert out.mapping["counterpartyName"] == ["Particulars"]


def test_legacy_xls_and_semicolon_csv() -> None:
    xls = extract("legacy_bills.xls")
    assert [r.draft.values.total for r in xls.rows] == [Decimal("15000.00"), Decimal("8250.50")]
    assert xls.rows[0].draft.values.invoice_date == date(2026, 8, 5)  # dd/mm proven by "18/08/2026"
    assert all("ambiguous_date" not in issue_codes(r) for r in xls.rows)
    assert all(r.draft.values.subtotal is None for r in xls.rows)  # no column → None, not 0

    csv_out = extract("purchase_bills.csv", record_type="purchase_invoice")
    assert csv_out.rows[0].draft.values.counterparty_name == "Bharat Wholesale Supplies"
    assert csv_out.rows[0].draft.values.payment_references == ["NEFT N12345678"]


def test_problem_rows_each_flag_the_right_issue() -> None:
    out = extract("sales_with_problems.csv")
    by_inv = {(r.draft.values.invoice_number, r.index): r for r in out.rows}
    rows = out.rows
    assert issue_codes(rows[0]).isdisjoint({"missing_required", "total_mismatch"})
    assert rows[0].draft.values.total == Decimal("11800.00")  # "₹11,800.00"
    assert "missing_required" in issue_codes(rows[1]) and rows[1].draft.values.total is None
    assert "total_mismatch" in issue_codes(rows[2])
    assert "duplicate_in_file" in issue_codes(rows[3])
    assert (
        "missing_required" in issue_codes(rows[4])
        and rows[4].draft.values.counterparty_name is None
    )
    assert "unparseable_date" in issue_codes(rows[5])
    assert "due_before_invoice" in issue_codes(rows[6]) and rows[
        6
    ].draft.values.subtotal == Decimal("500.00")
    assert (
        rows[6].draft.values.payment_status == "unknown"
        and rows[6].draft.values.document_payment_status == "paid"
    )
    assert (
        "missing_required" in issue_codes(rows[7]) and rows[7].draft.values.invoice_number is None
    )
    assert by_inv  # every row kept, none silently dropped
    assert len(rows) == 8


def test_unknown_columns_need_mapping_then_work() -> None:
    out = extract("unknown_columns.csv")
    assert out.status == "needs_mapping" and out.rows == []
    assert out.columns == ["Col1", "Col2", "Col3", "Col4"]
    assert out.sample_rows[0]["Col2"] == "Patel Agencies"
    mapping = {
        "invoiceNumber": ["Col1"],
        "counterpartyName": ["Col2"],
        "invoiceDate": ["Col3"],
        "total": ["Col4"],
    }
    mapped = extract("unknown_columns.csv", column_mapping=mapping)
    assert mapped.status == "needs_review"
    assert [r.draft.values.total for r in mapped.rows] == [Decimal("1180.00"), Decimal("590.00")]
    with pytest.raises(IngestionError) as info:
        extract("unknown_columns.csv", column_mapping={"total": ["Nope"]})
    assert info.value.code == "invalid_mapping"


# --- PDFs and images ----------------------------------------------------------------------------


def test_digital_pdf_uses_text_layer_not_ocr() -> None:
    out = extract("invoice_digital.pdf", ocr=ExplodingOcr())
    assert out.method == "text_layer" and out.ocr_pages == 0
    v = out.rows[0].draft.values
    assert (v.invoice_number, v.counterparty_name) == ("SGS/2026/0457", "Deshmukh Caterers")
    assert (v.invoice_date, v.due_date) == (date(2026, 9, 18), date(2026, 10, 18))
    assert (v.subtotal, v.tax, v.total) == (
        Decimal("13380.00"),
        Decimal("669.00"),
        Decimal("14049.00"),
    )
    assert v.payment_status == "unknown" and v.document_payment_status == "unpaid"
    assert not out.rows[0].draft.has_errors
    assert out.rows[0].source.page == 1 and out.rows[0].source.method == "text_layer"


def test_scanned_pdf_goes_through_ocr_provider() -> None:
    ocr = FakeOcr(INVOICE_TEXT)
    out = extract("invoice_scanned.pdf", ocr=ocr)
    assert ocr.calls == 1 and out.method == "ocr" and out.ocr_pages == 1
    assert out.rows[0].draft.values.total == Decimal("14049.00")
    assert out.rows[0].draft.confidence < 0.9  # OCR confidence lowers field confidence


def test_force_ocr_strategy() -> None:
    ocr = FakeOcr(INVOICE_TEXT)
    extract("invoice_digital.pdf", ocr=ocr, pdf_strategy="ocr")
    assert ocr.calls == 1


def test_ocr_unavailable_fails_clearly() -> None:
    with pytest.raises(IngestionError) as info:
        extract("invoice_scanned.pdf", ocr=UnavailableOcrProvider())
    assert info.value.code == "ocr_unavailable"


def test_low_quality_ocr_is_flagged() -> None:
    out = extract("bill_photo.png", ocr=FakeOcr(INVOICE_TEXT, confidence=0.4))
    assert any(w.code == "low_ocr_quality" for w in out.warnings)
    assert any(i.code == "low_confidence" for i in out.rows[0].draft.issues)


def test_nothing_found_gives_blank_row_to_fill() -> None:
    out = extract("bill_photo.png", ocr=FakeOcr("Thank you for shopping with us"))
    assert len(out.rows) == 1 and out.rows[0].draft.has_errors
    assert any(w.code == "nothing_extracted" for w in out.warnings)


def test_llm_provider_falls_back_to_rules() -> None:
    path = SAMPLES / "invoice_digital.pdf"
    out = run_extraction(
        path.read_bytes(),
        extension=".pdf",
        options=ExtractionOptions(),
        ocr=ExplodingOcr(),
        extractor=LlmExtractionProvider(),
        today=TODAY,
    )
    assert any(w.code == "extractor_fallback" for w in out.warnings)
    assert out.rows[0].draft.values.invoice_number == "SGS/2026/0457"


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract not installed")
class TestRealTesseract:
    def test_scanned_pdf(self) -> None:
        out = extract("invoice_scanned.pdf", ocr=TesseractOcrProvider())
        v = out.rows[0].draft.values
        assert v.invoice_number == "SGS/2026/0457"
        assert v.total == Decimal("14049.00")
        assert not out.rows[0].draft.has_errors

    def test_photo_with_split_invoice_number(self) -> None:
        out = extract("bill_photo.png", ocr=TesseractOcrProvider(), record_type="purchase_invoice")
        v = out.rows[0].draft.values
        assert v.counterparty_name == "Bharat Wholesale Supplies"
        assert v.total == Decimal("23600.00") and v.tax == Decimal("3600.00")
        assert v.invoice_number == "BWS/91/2026"
        assert (
            out.rows[0].draft.field_confidence["invoiceNumber"] < 0.6
        )  # repaired → user must check


# --- Malformed files ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("malformed/corrupt.xlsx", "malformed_file"),
        ("malformed/truncated.pdf", "malformed_file"),
        ("malformed/password_protected.pdf", "password_protected"),
        ("malformed/header_only.csv", "empty_file"),
        ("malformed/ragged.csv", "malformed_file"),
    ],
)
def test_malformed_files_fail_with_clear_codes(name: str, code: str) -> None:
    with pytest.raises(IngestionError) as info:
        extract(name)
    assert info.value.code == code
    assert info.value.message


def test_xlsx_zip_bomb_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spreadsheet, "MAX_XLSX_UNCOMPRESSED", 1000)
    with pytest.raises(IngestionError) as info:
        extract("sales_register.xlsx")
    assert info.value.code == "file_too_complex"


def test_xlsx_without_workbook_is_rejected() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<x/>")
    with pytest.raises(IngestionError) as info:
        run_extraction(
            buf.getvalue(),
            extension=".xlsx",
            options=ExtractionOptions(),
            ocr=FakeOcr(),
            extractor=RuleBasedExtractor(),
            today=TODAY,
        )
    assert info.value.code == "malformed_file"


def test_row_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spreadsheet, "MAX_ROWS", 2)
    with pytest.raises(IngestionError) as info:
        extract("sales_register.xlsx")
    assert info.value.code == "too_many_rows"
