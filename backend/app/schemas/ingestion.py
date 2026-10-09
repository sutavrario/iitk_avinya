"""API models for document ingestion. Amounts are decimal strings (exact), dates ISO strings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import ApiModel, InputModel

RecordType = Literal["sales_invoice", "purchase_invoice"]
PaymentStatus = Literal["unknown", "unpaid", "partially_paid", "paid"]
DocumentStatus = Literal[
    "uploaded",  # stored before ingestion existed; can be processed on demand
    "queued",
    "processing",
    "needs_mapping",
    "needs_review",
    "completed",
    "failed",
]
FieldName = Literal[
    "invoiceNumber", "counterpartyName", "invoiceDate", "dueDate", "currency",
    "subtotal", "tax", "total", "paymentStatus", "paymentReference",
]  # fmt: skip


class ValidationIssue(ApiModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    field: str | None = None
    suggested_value: str | None = None
    related_record_id: str | None = None


class SourceReference(ApiModel):
    """Points back into the preserved original file."""

    document_id: str
    file_name: str
    storage_path: str
    method: Literal["spreadsheet", "text_layer", "ocr", "llm"]
    sheet_name: str | None = None
    row_number: int | None = None
    page: int | None = None
    snippet: str | None = None


class NormalizedInvoice(ApiModel):
    """The normalized invoice schema shared by drafts and confirmed records.

    Missing values are `null`, never 0. `paymentStatus` is the *confirmed* status (default
    "unknown"); `documentPaymentStatus` is only what the document claimed.
    """

    invoice_number: str | None
    document_id: str | None
    record_type: RecordType
    counterparty_name: str | None  # customer (sales) or supplier (purchase)
    invoice_date: date | None
    due_date: date | None
    currency: str | None
    subtotal: Decimal | None
    tax: Decimal | None
    total: Decimal | None
    payment_status: PaymentStatus = "unknown"
    document_payment_status: str | None = None
    payment_references: list[str] = []
    confidence: float
    field_confidence: dict[str, float] = {}
    issues: list[ValidationIssue] = []
    source: SourceReference | None = None


class ExtractedRowOut(ApiModel):
    id: str
    index: int
    invoice: NormalizedInvoice
    raw: dict[str, str]  # values exactly as found in the file
    edited_fields: list[str]
    excluded: bool
    allow_duplicate: bool
    confirmed_record_id: str | None = None


class ProcessingInfo(ApiModel):
    run: int = 0
    attempts: int = 0
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    method: str | None = None
    ocr_pages: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExtractionInfo(ApiModel):
    sheet_name: str | None = None
    sheet_names: list[str] = []
    columns: list[str] = []
    sample_rows: list[dict[str, str]] = []
    header_row_number: int | None = None
    mapping: dict[str, list[str]] = {}
    mapping_confidence: dict[str, float] = {}
    warnings: list[ValidationIssue] = []
    row_count: int = 0
    error_row_count: int = 0


class DocumentDetailOut(ApiModel):
    id: str
    file_name: str
    size_bytes: int
    kind: Literal["spreadsheet", "pdf", "image"]
    content_type: str
    status: DocumentStatus
    record_type: RecordType
    uploaded_at: datetime
    uploaded_by: str | None = None
    duplicate_of_document_id: str | None = None
    processing: ProcessingInfo
    extraction: ExtractionInfo | None = None
    confirmed_count: int = 0


class ProcessRequest(InputModel):
    record_type: RecordType | None = None
    column_mapping: dict[FieldName, Annotated[list[str], Field(max_length=6)]] | None = None
    sheet_name: Annotated[str | None, Field(max_length=100)] = None
    force_ocr: bool = False


class RowUpdate(InputModel):
    """User corrections. Values are strings exactly as typed; `null` clears a field."""

    values: dict[FieldName, Annotated[str | None, Field(max_length=200)]] | None = None
    payment_status: PaymentStatus | None = None
    payment_references: (
        Annotated[list[Annotated[str, Field(max_length=60)]], Field(max_length=10)] | None
    ) = None
    excluded: bool | None = None
    allow_duplicate: bool | None = None


class ConfirmRequest(InputModel):
    row_ids: Annotated[list[str], Field(max_length=5000)] | None = (
        None  # default: all included rows
    )


class ConfirmRowResult(ApiModel):
    row_id: str
    outcome: Literal["created", "already_confirmed", "duplicate", "has_errors", "excluded"]
    record_id: str | None = None
    message: str | None = None


class ConfirmResponse(ApiModel):
    results: list[ConfirmRowResult]
    created: int
    document_status: DocumentStatus
