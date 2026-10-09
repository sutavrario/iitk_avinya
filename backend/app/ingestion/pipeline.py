"""Entry point: bytes in, reviewable drafts out. No Firestore/Storage access here."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.ingestion.drafts import Draft, Issue, build_draft, mark_in_file_duplicates
from app.ingestion.errors import IngestionError
from app.ingestion.models import RawRecord, SourceRef
from app.ingestion.normalize import infer_date_order
from app.ingestion.ocr import OcrProvider
from app.ingestion.pdf import PdfTextStrategy, extract_image_text, extract_pdf_pages
from app.ingestion.spreadsheet import (
    Mapping,
    load_table,
    rows_to_records,
    suggest_mapping,
    validate_mapping,
)
from app.ingestion.text_extractor import ExtractionProvider, RuleBasedExtractor

RecordType = Literal["sales_invoice", "purchase_invoice"]
OutcomeStatus = Literal["needs_mapping", "needs_review"]


@dataclass
class ExtractionOptions:
    record_type: RecordType = "sales_invoice"
    column_mapping: Mapping | None = None
    sheet_name: str | None = None
    pdf_strategy: PdfTextStrategy = "auto"


@dataclass
class DraftRow:
    row_id: str
    index: int
    draft: Draft
    source: SourceRef
    # Day/month order used for this row's dates, so later edits re-parse the same way.
    date_orders: dict[str, str | None] = field(default_factory=dict)


@dataclass
class ExtractionOutcome:
    status: OutcomeStatus
    method: str
    rows: list[DraftRow] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    # Spreadsheet-only details for the column-mapping step
    sheet_name: str | None = None
    sheet_names: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    sample_rows: list[dict[str, str]] = field(default_factory=list)
    header_row_number: int | None = None
    mapping: Mapping = field(default_factory=dict)
    mapping_confidence: dict[str, float] = field(default_factory=dict)
    ocr_pages: int = 0


def row_id_for(index: int) -> str:
    return f"row{index:05d}"


def run_extraction(
    content: bytes,
    *,
    extension: str,
    options: ExtractionOptions,
    ocr: OcrProvider,
    extractor: ExtractionProvider,
    today: date,
) -> ExtractionOutcome:
    if extension in {".csv", ".xlsx", ".xls"}:
        return _spreadsheet(content, extension, options, today)
    if extension == ".pdf":
        pages = extract_pdf_pages(content, ocr, options.pdf_strategy)
    elif extension in {".png", ".jpg", ".jpeg"}:
        pages = extract_image_text(content, ocr)
    else:
        raise IngestionError("unsupported_file_type", "This file type can't be processed.")

    outcome = ExtractionOutcome(
        status="needs_review",
        method="ocr" if any(p.method == "ocr" for p in pages) else "text_layer",
    )
    outcome.ocr_pages = sum(p.method == "ocr" for p in pages)
    try:
        records = extractor.extract(pages, options.record_type)
    except IngestionError as exc:
        if exc.code != "llm_unavailable":
            raise
        outcome.warnings.append(
            Issue(
                "extractor_fallback",
                "info",
                "AI extraction isn't configured; used the built-in reader.",
            )
        )
        records = RuleBasedExtractor().extract(pages, options.record_type)

    if not records:
        # Text exists but no recognisable fields: give the user a blank row to fill in.
        records = [RawRecord(values={}, source=SourceRef(method=outcome.method, page=1))]  # type: ignore[arg-type]
        outcome.warnings.append(
            Issue(
                "nothing_extracted",
                "warning",
                "We couldn't find invoice details automatically. Fill them in from the original document.",
            )
        )
    low = [p.page for p in pages if p.method == "ocr" and p.confidence < 0.6]
    if low:
        outcome.warnings.append(
            Issue(
                "low_ocr_quality",
                "warning",
                f"Page {', '.join(map(str, low))} was hard to read. Check every value against the original.",
            )
        )
    outcome.rows = _drafts(records, options.record_type, today, per_document=True)
    return outcome


def _spreadsheet(
    content: bytes, extension: str, options: ExtractionOptions, today: date
) -> ExtractionOutcome:
    table = load_table(content, extension, options.sheet_name)
    suggestion = suggest_mapping(table)
    outcome = ExtractionOutcome(
        status="needs_review",
        method="spreadsheet",
        sheet_name=table.sheet_name,
        sheet_names=table.sheet_names,
        columns=table.columns,
        sample_rows=[{c: _cell(row.get(c)) for c in table.columns} for _, row in table.rows[:5]],
        header_row_number=table.header_row_number,
    )
    if options.column_mapping is not None:
        mapping = {f: cols for f, cols in options.column_mapping.items() if cols}
        validate_mapping(mapping, table.columns)
        confidence = {f: 1.0 for f in mapping}  # confirmed by the user
    else:
        mapping, confidence = suggestion.mapping, suggestion.confidence
        if suggestion.needs_review:
            outcome.status = "needs_mapping"
    outcome.mapping, outcome.mapping_confidence = mapping, confidence
    if outcome.status == "needs_mapping":
        return outcome

    records = rows_to_records(table, mapping, confidence)
    if not records:
        raise IngestionError("no_records_found", "No invoice rows were found in this sheet.")
    outcome.rows = _drafts(records, options.record_type, today)
    _collapse_currency_warning(outcome)
    return outcome


def _date_orders(records: list[RawRecord], per_document: bool) -> list[dict[str, str | None]]:
    fields = ("invoiceDate", "dueDate")
    if per_document:  # PDFs: each record's own dates are the evidence
        return [
            {f: infer_date_order([r.values.get(x) for x in fields]) for f in fields}
            for r in records
        ]
    column = {f: infer_date_order([r.values.get(f) for r in records]) for f in fields}
    return [column for _ in records]


def _drafts(
    records: list[RawRecord], record_type: str, today: date, *, per_document: bool = False
) -> list[DraftRow]:
    orders = _date_orders(records, per_document)
    rows = [
        DraftRow(
            row_id=row_id_for(i),
            index=i,
            draft=build_draft(
                r.values,
                record_type=record_type,
                today=today,
                field_confidence=r.field_confidence,
                payment_references=r.payment_references,
                date_orders=orders[i],
            ),
            source=r.source,
            date_orders=orders[i],
        )
        for i, r in enumerate(records)
    ]
    mark_in_file_duplicates([(r.row_id, r.draft) for r in rows])
    return rows


def _collapse_currency_warning(outcome: ExtractionOutcome) -> None:
    """If no row had any currency information, say so once for the document, not on every row."""

    def assumed(r: DraftRow) -> bool:
        return any(i.code == "currency_assumed" for i in r.draft.issues)

    if len(outcome.rows) > 1 and all(assumed(r) for r in outcome.rows):
        for r in outcome.rows:
            r.draft.issues = [i for i in r.draft.issues if i.code != "currency_assumed"]
        outcome.warnings.append(
            Issue(
                "currency_assumed",
                "warning",
                f"No currency was found in this file; all amounts were read as {outcome.rows[0].draft.values.currency}.",
                "currency",
            )
        )


def _cell(value: Any) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())[:10]
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)[:60]
