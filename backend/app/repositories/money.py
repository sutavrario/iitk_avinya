"""Money is stored as integer paise in Firestore to avoid floating-point drift."""

from decimal import ROUND_HALF_UP, Decimal


def to_paise(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_paise(paise: int | None) -> float:
    return 0.0 if paise is None else paise / 100
