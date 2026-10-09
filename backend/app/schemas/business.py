from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import InputModel

LanguageCode = Literal["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa"]
BusinessGoal = Literal[
    "track_cash_flow",
    "collect_payments_faster",
    "reduce_expenses",
    "gst_compliance",
    "grow_sales",
    "manage_inventory",
    "get_loan_ready",
]
RoleName = Literal["owner", "admin", "member", "viewer"]

GSTIN_PATTERN = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"


class BusinessLocation(InputModel):
    city: Annotated[str, Field(min_length=1, max_length=80)]
    state: Annotated[str, Field(min_length=1, max_length=60)]
    pincode: Annotated[str | None, Field(default=None, pattern=r"^[1-9][0-9]{5}$")] = None


class BusinessProfileIn(InputModel):
    business_name: Annotated[str, Field(min_length=2, max_length=100)]
    industry: Annotated[str, Field(min_length=1, max_length=50)]
    business_type: Annotated[str, Field(max_length=50)] = ""
    location: BusinessLocation
    currency: Literal["INR"] = "INR"
    financial_year_start: Literal["april", "january"] = "april"
    payment_terms_days: Annotated[int | None, Field(ge=0, le=365)] = None
    goals: Annotated[list[BusinessGoal], Field(max_length=10)] = []
    preferred_language: LanguageCode = "en"
    gstin: Annotated[str | None, Field(default=None, pattern=GSTIN_PATTERN)] = None

    @field_validator("gstin", mode="before")
    @classmethod
    def _upper_gstin(cls, v: object) -> object:
        return v.strip().upper() or None if isinstance(v, str) else v

    @field_validator("goals")
    @classmethod
    def _dedupe_goals(cls, v: list[BusinessGoal]) -> list[BusinessGoal]:
        return list(dict.fromkeys(v))


class BusinessOut(BusinessProfileIn):
    """Business profile as returned to the client, plus server-owned fields."""

    # Ignore server-internal fields (ownerUid, createdBy, …) when building from Firestore data.
    model_config = ConfigDict(extra="ignore")

    id: str
    role: RoleName
    created_at: datetime
    updated_at: datetime
