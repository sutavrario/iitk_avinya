"""Spreadsheet parsing (CSV, .xlsx via openpyxl, .xls via xlrd) and column mapping."""

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd

from app.ingestion.errors import IngestionError
from app.ingestion.models import FIELDS, MULTI_COLUMN_FIELDS, REQUIRED_FIELDS, RawRecord, SourceRef
from app.ingestion.normalize import detect_currency, is_blank, parse_amount, parse_date

MAX_ROWS = 5000
MAX_COLUMNS = 100
HEADER_SCAN_ROWS = 20
MAX_XLSX_UNCOMPRESSED = 100 * 1024 * 1024
MAPPING_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class SheetTable:
    sheet_name: str | None
    sheet_names: list[str]
    columns: list[str]
    # (1-based row number in the original sheet, {column: raw value})
    rows: list[tuple[int, dict[str, Any]]]
    header_row_number: int


# --- Loading --------------------------------------------------------------------------------


def load_table(content: bytes, extension: str, sheet_name: str | None = None) -> SheetTable:
    frames: dict[str | None, pd.DataFrame]
    if extension == ".csv":
        frames = {None: _read_csv(content)}
    elif extension == ".xlsx":
        _check_xlsx_container(content)
        frames = _read_excel(content, "openpyxl")
    elif extension == ".xls":
        frames = _read_excel(content, "xlrd")
    else:
        raise IngestionError("unsupported_file_type", f"{extension} is not a spreadsheet.")

    names = [str(n) for n in frames if n is not None]
    if sheet_name is not None:
        if sheet_name not in frames:
            raise IngestionError("sheet_not_found", f"The sheet '{sheet_name}' isn't in this file.")
        chosen: str | None = sheet_name
    else:
        chosen = next((n for n, df in frames.items() if _non_empty_rows(df) >= 2), None)
        if chosen is None and None not in frames:
            raise IngestionError("empty_file", "This spreadsheet has no data rows.")
    df = frames[chosen]
    if _non_empty_rows(df) < 2:
        raise IngestionError(
            "empty_file", "This spreadsheet needs a header row and at least one data row."
        )
    if df.shape[1] > MAX_COLUMNS:
        raise IngestionError("too_many_columns", f"Sheets can have at most {MAX_COLUMNS} columns.")
    return _to_table(df, chosen, names)


def _read_csv(content: bytes) -> pd.DataFrame:
    if b"\x00" in content[:8192]:
        raise IngestionError("malformed_file", "This doesn't look like a text CSV file.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - cp1252 decodes almost anything
        raise IngestionError("malformed_file", "Couldn't read the text encoding of this CSV.")
    try:
        delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    try:
        return pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            header=None,
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=False,
            engine="python",
            nrows=MAX_ROWS + HEADER_SCAN_ROWS + 1,
        )
    except (pd.errors.ParserError, pd.errors.EmptyDataError, csv.Error) as exc:
        raise IngestionError(
            "malformed_file", "This CSV file is malformed (inconsistent columns or quotes)."
        ) from exc


def _check_xlsx_container(content: bytes) -> None:
    """Reject corrupt archives and zip bombs before handing the file to openpyxl."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = set(zf.namelist())
            total = sum(i.file_size for i in zf.infolist())
    except zipfile.BadZipFile as exc:
        raise IngestionError(
            "malformed_file", "This .xlsx file is damaged or isn't really an Excel file."
        ) from exc
    if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
        raise IngestionError(
            "malformed_file", "This .xlsx file is damaged or isn't really an Excel file."
        )
    if total > MAX_XLSX_UNCOMPRESSED:
        raise IngestionError(
            "file_too_complex",
            "This workbook is too large to process. Split it into smaller files.",
        )


def _read_excel(content: bytes, engine: str) -> dict[str | None, pd.DataFrame]:
    try:
        sheets = pd.read_excel(
            io.BytesIO(content),
            sheet_name=None,
            header=None,
            engine=engine,
            nrows=MAX_ROWS + HEADER_SCAN_ROWS + 1,
        )  # type: ignore[call-overload]
    except Exception as exc:  # openpyxl/xlrd raise many different types for bad files
        raise IngestionError(
            "malformed_file",
            "This spreadsheet couldn't be opened. It may be damaged or password-protected.",
        ) from exc
    return {str(k): v for k, v in sheets.items()}


def _non_empty_rows(df: pd.DataFrame) -> int:
    return sum(1 for _, row in df.iterrows() if any(not is_blank(v) for v in row.tolist()))


# --- Header detection -----------------------------------------------------------------------

_SYNONYMS: dict[str, list[tuple[str, float]]] = {
    "invoiceNumber": [
        ("invoice no", 1),
        ("invoice number", 1),
        ("invoice num", 1),
        ("inv no", 1),
        ("invoice", 0.7),
        ("invoice id", 1),
        ("bill no", 1),
        ("bill number", 1),
        ("voucher no", 0.95),
        ("vch no", 0.95),
        ("document no", 0.8),
        ("doc no", 0.8),
        ("receipt no", 0.7),
        ("invoice #", 1),
        ("inv #", 1),
    ],
    "counterpartyName": [
        ("customer name", 1),
        ("customer", 0.95),
        ("party name", 1),
        ("party a c name", 1),
        ("party", 0.9),
        ("buyer", 0.9),
        ("buyer name", 1),
        ("client", 0.9),
        ("client name", 1),
        ("billed to", 0.9),
        ("bill to", 0.9),
        ("supplier", 0.95),
        ("supplier name", 1),
        ("vendor", 0.95),
        ("vendor name", 1),
        ("seller", 0.8),
        ("particulars", 0.75),
        ("name", 0.6),
        ("account", 0.5),
    ],
    "invoiceDate": [
        ("invoice date", 1),
        ("inv date", 1),
        ("bill date", 1),
        ("voucher date", 0.95),
        ("vch date", 0.95),
        ("doc date", 0.9),
        ("issue date", 0.9),
        ("dated", 0.8),
        ("date", 0.75),
    ],
    "dueDate": [
        ("due date", 1),
        ("due on", 0.95),
        ("payment due", 0.9),
        ("due by", 0.9),
        ("due", 0.7),
    ],
    "currency": [("currency", 1), ("curr", 0.9), ("ccy", 0.9)],
    "subtotal": [
        ("subtotal", 1),
        ("sub total", 1),
        ("taxable value", 1),
        ("taxable amount", 1),
        ("taxable amt", 1),
        ("amount before tax", 1),
        ("assessable value", 0.9),
        ("basic amount", 0.85),
    ],
    "tax": [
        ("total tax", 1),
        ("tax amount", 1),
        ("gst amount", 1),
        ("total gst", 1),
        ("gst", 0.9),
        ("tax", 0.85),
        ("cgst", 0.9),
        ("sgst", 0.9),
        ("igst", 0.9),
        ("utgst", 0.9),
        ("cess", 0.8),
        ("vat", 0.8),
    ],
    "total": [
        ("grand total", 1),
        ("total amount", 1),
        ("invoice value", 1),
        ("invoice amount", 1),
        ("invoice total", 1),
        ("gross total", 0.95),
        ("bill amount", 0.95),
        ("amount payable", 0.95),
        ("total", 0.85),
        ("net amount", 0.7),
        ("amount", 0.65),
        ("value", 0.5),
    ],
    "paymentStatus": [("payment status", 1), ("status", 0.85), ("paid unpaid", 0.9), ("paid", 0.6)],
    "paymentReference": [
        ("utr", 1),
        ("utr no", 1),
        ("payment reference", 1),
        ("payment ref", 1),
        ("transaction id", 0.95),
        ("txn id", 0.95),
        ("cheque no", 0.95),
        ("chq no", 0.95),
        ("reference", 0.7),
        ("ref no", 0.7),
    ],
}
_TAX_COMPONENTS = {"cgst", "sgst", "igst", "utgst", "cess"}


def _norm_header(text: Any) -> str:
    t = str(text).lower().replace("#", " # ")
    t = re.sub(r"[^a-z0-9#]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def header_score(header: str) -> dict[str, float]:
    """Score how well a column header matches each field (0..1)."""
    h = _norm_header(header)
    if not h:
        return {}
    scores: dict[str, float] = {}
    for field, synonyms in _SYNONYMS.items():
        best = 0.0
        for syn, weight in synonyms:
            if h == syn:
                best = max(best, weight)
            elif re.search(rf"(^| ){re.escape(syn)}( |$)", h):
                best = max(best, weight * 0.85)
        if best:
            scores[field] = round(best, 3)
    return scores


def _to_table(df: pd.DataFrame, sheet_name: str | None, sheet_names: list[str]) -> SheetTable:
    raw_rows = [row.tolist() for _, row in df.iterrows()]
    header_idx = _find_header_row(raw_rows)
    header = raw_rows[header_idx]
    columns: list[str] = []
    for i, cell in enumerate(header):
        name = re.sub(r"\s+", " ", str(cell)).strip() if not is_blank(cell) else ""
        if not name or name in columns:
            name = f"{name or 'Column'} ({_col_letter(i)})"
        columns.append(name)

    rows: list[tuple[int, dict[str, Any]]] = []
    for idx in range(header_idx + 1, len(raw_rows)):
        values = raw_rows[idx]
        if all(is_blank(v) for v in values):
            continue
        rows.append((idx + 1, {columns[i]: v for i, v in enumerate(values) if i < len(columns)}))
    if len(rows) > MAX_ROWS:
        raise IngestionError(
            "too_many_rows", f"Files can have at most {MAX_ROWS} rows. Split it into smaller files."
        )
    if not rows:
        raise IngestionError("empty_file", "No data rows were found below the header row.")
    return SheetTable(sheet_name, sheet_names, columns, rows, header_idx + 1)


def _find_header_row(rows: list[list[Any]]) -> int:
    best_idx, best_score = None, 0.0
    for idx, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        cells = [c for c in row if not is_blank(c)]
        if len(cells) < 2:
            continue
        text_cells = [c for c in cells if isinstance(c, str) and parse_amount(c) is None]
        matched = sum(max(header_score(c).values(), default=0) for c in text_cells)
        score = matched * 2 + len(text_cells) * 0.1
        if score > best_score:
            best_idx, best_score = idx, score
    if best_idx is None:
        best_idx = next((i for i, r in enumerate(rows) if any(not is_blank(c) for c in r)), 0)
    return best_idx


def _col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# --- Column mapping ---------------------------------------------------------------------------

Mapping = dict[str, list[str]]


@dataclass
class MappingSuggestion:
    mapping: Mapping
    confidence: dict[str, float]

    @property
    def needs_review(self) -> bool:
        return any(
            f not in self.mapping or self.confidence.get(f, 0) < MAPPING_CONFIDENCE_THRESHOLD
            for f in REQUIRED_FIELDS
        )


def suggest_mapping(table: SheetTable) -> MappingSuggestion:
    sample = [r for _, r in table.rows[:25]]
    candidates: list[tuple[float, str, str]] = []
    for column in table.columns:
        scores = header_score(column)
        if not scores:
            continue
        best = max(scores.values())
        for field, score in scores.items():
            # A column is only a candidate for fields close to its best match, so
            # "Tax Amount" never becomes `total` and "Invoice Date" never `invoiceNumber`.
            if score < best * 0.9:
                continue
            candidates.append(
                (score * _value_fit(field, [r.get(column) for r in sample]), field, column)
            )
    candidates.sort(reverse=True)

    mapping: Mapping = {}
    confidence: dict[str, float] = {}
    used: set[str] = set()
    for score, field, column in candidates:
        if column in used or score < 0.35:
            continue
        if field in MULTI_COLUMN_FIELDS:
            continue  # handled below
        if field in mapping:
            continue
        mapping[field] = [column]
        confidence[field] = round(score, 2)
        used.add(column)

    tax_cols = _suggest_tax_columns(table.columns, used)
    if tax_cols:
        mapping["tax"] = tax_cols
        confidence["tax"] = 0.85
    return MappingSuggestion(mapping, confidence)


def _suggest_tax_columns(columns: list[str], used: set[str]) -> list[str]:
    free = [c for c in columns if c not in used]
    totals = [
        c
        for c in free
        if _norm_header(c) in {"total tax", "tax amount", "gst amount", "total gst", "gst", "tax"}
    ]
    if totals:
        return totals[:1]  # a total-tax column already includes the components; don't double count
    return [c for c in free if set(_norm_header(c).split()) & _TAX_COMPONENTS]


def _value_fit(field: str, values: list[Any]) -> float:
    """Down-weight a header match when the column's values don't fit the field's type."""
    present = [v for v in values if not is_blank(v)]
    if not present:
        return 0.6
    if field in {"invoiceDate", "dueDate"}:
        ok = sum(parse_date(v).value is not None for v in present)
    elif field in {"subtotal", "tax", "total"}:
        ok = sum(parse_amount(v) is not None for v in present)
    else:
        return 1.0
    ratio = ok / len(present)
    return 1.0 if ratio >= 0.8 else 0.5 + ratio / 2


def validate_mapping(mapping: Mapping, columns: list[str]) -> None:
    for field, cols in mapping.items():
        if field not in FIELDS:
            raise IngestionError("invalid_mapping", f"Unknown field '{field}'.")
        if not cols:
            continue
        if len(cols) > 1 and field not in MULTI_COLUMN_FIELDS:
            raise IngestionError("invalid_mapping", f"'{field}' can be mapped to only one column.")
        for c in cols:
            if c not in columns:
                raise IngestionError("invalid_mapping", f"Column '{c}' isn't in this sheet.")


# --- Rows → raw records -----------------------------------------------------------------------

_SUMMARY_ROW = re.compile(r"^\s*(grand\s+)?(sub\s*)?totals?\b", re.IGNORECASE)


def rows_to_records(
    table: SheetTable, mapping: Mapping, mapping_confidence: dict[str, float]
) -> list[RawRecord]:
    records: list[RawRecord] = []
    amount_cols = [c for f in ("subtotal", "tax", "total") for c in mapping.get(f, [])]
    for row_number, row in table.rows:
        if _is_summary_row(row, mapping):
            continue
        values: dict[str, Any] = {}
        for field, cols in mapping.items():
            if not cols:
                continue
            if field in MULTI_COLUMN_FIELDS and len(cols) > 1:
                combined = _sum_columns([row.get(c) for c in cols])
                if combined is not None:
                    values[field] = combined
            else:
                v = row.get(cols[0])
                if not is_blank(v):
                    values[field] = v
        if "currency" not in values:
            detected = detect_currency(*(row.get(c) for c in amount_cols))
            if detected:
                values["currency"] = detected
        refs = _split_refs(values.pop("paymentReference", None))
        records.append(
            RawRecord(
                values=values,
                source=SourceRef(
                    method="spreadsheet", sheet_name=table.sheet_name, row_number=row_number
                ),
                field_confidence={f: mapping_confidence.get(f, 0.9) for f in values},
                payment_references=refs,
            )
        )
    return records


def _is_summary_row(row: dict[str, Any], mapping: Mapping) -> bool:
    inv_cols = mapping.get("invoiceNumber") or []
    inv_col = inv_cols[0] if inv_cols else None
    if inv_col and not is_blank(row.get(inv_col)):
        return False
    first_text = next((str(v) for v in row.values() if not is_blank(v)), "")
    return bool(_SUMMARY_ROW.match(first_text))


def _sum_columns(values: list[Any]) -> Any:
    present = [v for v in values if not is_blank(v)]
    if not present:
        return None
    parsed = [parse_amount(v) for v in present]
    if any(p is None for p in parsed):
        return " + ".join(str(v) for v in present)  # normalizer will flag it as unparseable
    return sum((p for p in parsed if p is not None), Decimal("0"))


def _split_refs(value: Any) -> list[str]:
    if is_blank(value):
        return []
    return [r.strip() for r in re.split(r"[;,|]", str(value)) if r.strip()][:10]
