"""Internal data structures passed between pipeline stages."""

from dataclasses import dataclass, field
from typing import Any, Literal

# Fields the pipeline can extract. Order matters for the mapping UI.
FIELDS: tuple[str, ...] = (
    "invoiceNumber",
    "counterpartyName",
    "invoiceDate",
    "dueDate",
    "currency",
    "subtotal",
    "tax",
    "total",
    "paymentStatus",
    "paymentReference",
)
REQUIRED_FIELDS: tuple[str, ...] = ("invoiceNumber", "counterpartyName", "invoiceDate", "total")
# Fields that may be mapped to several columns whose values are summed (e.g. CGST + SGST + IGST).
MULTI_COLUMN_FIELDS: frozenset[str] = frozenset({"tax"})

ExtractionMethod = Literal["spreadsheet", "text_layer", "ocr", "llm"]


@dataclass
class SourceRef:
    """Where in the original document a record came from."""

    method: ExtractionMethod
    sheet_name: str | None = None
    row_number: int | None = None  # 1-based, as shown in Excel
    page: int | None = None  # 1-based
    snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "sheetName": self.sheet_name,
            "rowNumber": self.row_number,
            "page": self.page,
            "snippet": self.snippet,
        }


@dataclass
class RawRecord:
    """Values exactly as found in the document, before normalization.

    `values[field]` is a string/number/date as read; a missing key means "not found",
    which is different from an empty or zero value.
    """

    values: dict[str, Any]
    source: SourceRef
    field_confidence: dict[str, float] = field(default_factory=dict)
    payment_references: list[str] = field(default_factory=list)


@dataclass
class PageText:
    page: int
    text: str
    method: Literal["text_layer", "ocr"]
    confidence: float  # 0..1 (1.0 for an embedded text layer)
