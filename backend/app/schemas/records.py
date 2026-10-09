from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas.common import ApiModel, InputModel

Money = Annotated[Decimal, Field(gt=0, le=Decimal("10000000000"), decimal_places=2)]
# "unknown": imported from a document and the payment status hasn't been confirmed by the user.
InvoiceStatus = Literal["paid", "unpaid", "partially_paid", "overdue", "unknown"]
RecordSource = Literal["manual", "upload"]
PaymentDirection = Literal["received", "paid"]
PaymentMethod = Literal["upi", "bank_transfer", "cash", "cheque", "card"]
ShortText = Annotated[str, Field(min_length=1, max_length=120)]


class InvoiceIn(InputModel):
    invoice_number: Annotated[str, Field(min_length=1, max_length=40)]
    customer_name: ShortText
    issue_date: date
    due_date: date
    amount: Money
    gst_amount: Annotated[Decimal | None, Field(ge=0, decimal_places=2)] = None
    # "overdue" is derived on read from dueDate; clients may not set it.
    status: Literal["unpaid", "partially_paid", "paid"] = "unpaid"

    @model_validator(mode="after")
    def _check(self) -> "InvoiceIn":
        if self.due_date < self.issue_date:
            raise ValueError("dueDate can't be before issueDate")
        if self.gst_amount is not None and self.gst_amount >= self.amount:
            raise ValueError("gstAmount must be less than amount")
        return self


class InvoiceOut(ApiModel):
    id: str
    invoice_number: str
    customer_name: str
    issue_date: date
    due_date: date | None  # unknown for some imported invoices; never guessed
    amount: float
    subtotal: float | None = None
    gst_amount: float | None = None
    currency: str = "INR"
    status: InvoiceStatus
    payment_references: list[str] = []
    source: RecordSource
    document_id: str | None = None
    created_at: datetime


IsoDate = date  # alias: a field named `date` would otherwise shadow the type in the class body


class ExpenseOut(ApiModel):
    id: str
    invoice_number: str
    supplier_name: str
    date: IsoDate
    due_date: IsoDate | None
    currency: str
    subtotal: float | None
    tax: float | None
    total: float
    payment_status: Literal["paid", "unpaid", "partially_paid", "unknown"]
    payment_references: list[str] = []
    document_id: str | None
    created_at: datetime


class PaymentIn(InputModel):
    date: date
    party_name: ShortText
    direction: PaymentDirection
    amount: Money
    method: PaymentMethod
    reference: Annotated[str | None, Field(max_length=60)] = None
    invoice_number: Annotated[str | None, Field(max_length=40)] = None

    @model_validator(mode="after")
    def _not_future(self) -> "PaymentIn":
        # Allow one day of slack for timezone differences (IST vs UTC).
        if self.date > datetime.now(UTC).date() + timedelta(days=1):
            raise ValueError("Payment date can't be in the future")
        return self


class PaymentOut(ApiModel):
    id: str
    date: date
    party_name: str
    direction: PaymentDirection
    amount: float
    method: PaymentMethod
    reference: str | None = None
    invoice_number: str | None = None
    source: RecordSource
    created_at: datetime
