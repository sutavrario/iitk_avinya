"""Turn raw strings into typed values. Missing or unparseable values become None plus an
issue — never zero, never a guess presented as fact."""

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

# --- Amounts --------------------------------------------------------------------------------

_CURRENCY_TOKENS = re.compile(r"(₹|rs\.?|inr|\$|usd|€|eur|£|gbp)", re.IGNORECASE)
_AMOUNT_CHARS = re.compile(r"[^0-9.\-]")


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:  # NaN
        return True
    return isinstance(value, str) and value.strip() in {
        "",
        "-",
        "—",
        "nan",
        "NaN",
        "None",
        "N/A",
        "n/a",
        "NA",
    }


def parse_amount(value: Any) -> Decimal | None:
    """Parse '₹1,23,456.50', 'Rs. 500', '(1,200)', 1234.5 → Decimal. Returns None if unparseable.

    Raises nothing; callers decide whether None is an error. Blank → None (not zero).
    """
    if is_blank(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except InvalidOperation:
            return None
    text = str(value).strip()
    if text.endswith("/-"):  # Indian "Rs. 500/-" means "500 only", not negative
        text = text[:-2].strip()
    negative = (
        (text.startswith("(") and text.endswith(")")) or text.startswith("-") or text.endswith("-")
    )
    text = _CURRENCY_TOKENS.sub("", text)
    if re.search(r"[a-z]", text, re.IGNORECASE):
        return None  # "Col1", "INV-1001", "2 pcs" are not amounts
    cleaned = _AMOUNT_CHARS.sub("", text).strip("-")
    if not cleaned or cleaned.count(".") > 1 or not re.search(r"\d", cleaned):
        return None
    try:
        amount = Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -amount if negative else amount


def detect_currency(*values: Any) -> str | None:
    for value in values:
        if is_blank(value):
            continue
        text = str(value).lower()
        if "₹" in text or re.search(r"\b(inr|rs\.?|rupees?)\b", text) or "rs." in text:
            return "INR"
        if "$" in text or "usd" in text:
            return "USD"
        if "€" in text or "eur" in text:
            return "EUR"
        if "£" in text or "gbp" in text:
            return "GBP"
    return None


def normalize_currency_code(value: Any) -> str | None:
    if is_blank(value):
        return None
    text = str(value).strip().upper()
    if re.fullmatch(r"[A-Z]{3}", text):
        return text
    return detect_currency(value)


# --- Dates ----------------------------------------------------------------------------------

_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}
_EXCEL_EPOCH = date(1899, 12, 30)


class DateParse:
    __slots__ = ("value", "ambiguous")

    def __init__(self, value: date | None, ambiguous: bool = False) -> None:
        self.value = value
        self.ambiguous = ambiguous


DateOrder = str  # "dmy" | "mdy"
_NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\s*$")


def infer_date_order(values: list[Any]) -> DateOrder | None:
    """Look at a whole column (or document) to decide day/month order.

    One '31/01/2026' proves day-first; one '01/31/2026' proves month-first. Mixed or no
    evidence → None (each ambiguous value is then flagged for review).
    """
    dmy = mdy = False
    for v in values:
        if is_blank(v) or not isinstance(v, str):
            continue
        m = _NUMERIC_DATE.match(v)
        if not m:
            continue
        a, b = int(m[1]), int(m[2])
        dmy |= a > 12 >= b
        mdy |= b > 12 >= a
    if dmy and not mdy:
        return "dmy"
    if mdy and not dmy:
        return "mdy"
    return None


def parse_date(value: Any, order: DateOrder | None = None) -> DateParse:
    """Parse common Indian business date formats. Numeric dates are read day-first unless
    `order` says otherwise; without a known order, dd/mm vs mm/dd ambiguity is flagged."""
    if is_blank(value):
        return DateParse(None)
    if isinstance(value, datetime):
        return DateParse(value.date())
    if isinstance(value, date):
        return DateParse(value)
    if hasattr(value, "to_pydatetime"):  # pandas Timestamp
        return DateParse(value.to_pydatetime().date())
    if isinstance(value, int | float) and not isinstance(value, bool):
        # Excel serial date (only a plausible range, to avoid treating amounts as dates).
        if 20000 <= float(value) <= 80000:
            return DateParse(_EXCEL_EPOCH + timedelta(days=int(value)))
        return DateParse(None)

    text = str(value).strip().lower().replace(",", " ")
    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text)
    text = re.sub(r"\s+", " ", text)

    # ISO yyyy-mm-dd (optionally with time)
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if m:
        return _safe(int(m[1]), int(m[2]), int(m[3]))
    # dd-mm-yyyy / dd/mm/yy
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$", text)
    if m:
        first, second, y = int(m[1]), int(m[2]), _year(m[3])
        d, mo = (second, first) if order == "mdy" else (first, second)
        result = _safe(y, mo, d)
        result.ambiguous = (
            order is None and result.value is not None and d <= 12 and mo <= 12 and d != mo
        )
        return result
    # dd-Mon-yyyy / dd Mon yyyy / Mon dd yyyy
    m = re.match(r"^(\d{1,2})[-/ ]([a-z]{3})[a-z]*[-/ ](\d{2,4})$", text)
    if m and m[2] in _MONTHS:
        return _safe(_year(m[3]), _MONTHS[m[2]], int(m[1]))
    m = re.match(r"^([a-z]{3})[a-z]* (\d{1,2}) (\d{2,4})$", text)
    if m and m[1] in _MONTHS:
        return _safe(_year(m[3]), _MONTHS[m[1]], int(m[2]))
    return DateParse(None)


def _year(text: str) -> int:
    y = int(text)
    return y + 2000 if y < 100 else y


def _safe(y: int, mo: int, d: int) -> DateParse:
    try:
        return DateParse(date(y, mo, d))
    except ValueError:
        return DateParse(None)


# --- Text -----------------------------------------------------------------------------------


def clean_text(value: Any, max_len: int = 120) -> str | None:
    if is_blank(value):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Excel stores "1001" as 1001.0
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:max_len] or None


_PAID = re.compile(r"\b(paid|settled|received|cleared|fully paid)\b", re.IGNORECASE)
_UNPAID = re.compile(r"\b(unpaid|due|pending|outstanding|not paid|balance due)\b", re.IGNORECASE)
_PARTIAL = re.compile(r"\b(partial(ly)?|part[- ]paid)\b", re.IGNORECASE)


def parse_payment_status(value: Any) -> str | None:
    """What the *document* says about payment. This is evidence only — never used as the
    record's confirmed payment status without the user's review."""
    if is_blank(value):
        return None
    text = str(value)
    if _PARTIAL.search(text):
        return "partially_paid"
    if _UNPAID.search(text):
        return "unpaid"
    if _PAID.search(text):
        return "paid"
    return None


def normalize_key(text: str | None) -> str:
    """For duplicate detection: case/spacing/punctuation-insensitive."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())
