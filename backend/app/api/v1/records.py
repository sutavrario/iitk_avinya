from datetime import date

from fastapi import APIRouter, Query, status

from app.api.v1.deps import Db
from app.core.errors import ConflictError
from app.ingestion.drafts import dedupe_key
from app.repositories import collections as col
from app.repositories import records as records_repo
from app.repositories.money import to_paise
from app.schemas.records import ExpenseOut, InvoiceIn, InvoiceOut, PaymentIn, PaymentOut
from app.services.authorization import CanEdit, CanView
from app.services.ingestion_store import find_existing
from app.services.invoices import expense_to_api, invoice_to_api, payment_to_api

router = APIRouter(prefix="/businesses/{business_id}", tags=["records"])


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(access: CanView, db: Db) -> list[InvoiceOut]:
    today = date.today()
    docs = records_repo.list_records(db, col.INVOICES, access, order_by="issueDate")
    return [InvoiceOut.model_validate(invoice_to_api(d, today)) for d in docs]


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    body: InvoiceIn,
    access: CanEdit,
    db: Db,
    allow_duplicate: bool = Query(False, alias="allowDuplicate"),
) -> InvoiceOut:
    key = dedupe_key("sales_invoice", body.invoice_number, body.customer_name)
    if not allow_duplicate and key:
        existing = find_existing(db, access.business_id, "sales_invoice", [key])
        if key in existing:
            raise ConflictError(
                f"Invoice {body.invoice_number} for {body.customer_name} is already saved.",
                details={"existingRecordId": existing[key]},
                code="duplicate_invoice",
            )
    total = to_paise(body.amount)
    tax = to_paise(body.gst_amount) if body.gst_amount is not None else None
    doc = records_repo.create_record(
        db,
        col.INVOICES,
        access,
        {
            "invoiceNumber": body.invoice_number,
            "customerName": body.customer_name,
            "issueDate": body.issue_date.isoformat(),
            "dueDate": body.due_date.isoformat(),
            "amountPaise": total,
            "gstAmountPaise": tax,
            "status": body.status,
            "source": "manual",
            # Normalized fields shared with imported invoices.
            "recordType": "sales_invoice",
            "counterpartyName": body.customer_name,
            "currency": "INR",
            "totalPaise": total,
            "taxPaise": tax,
            "paymentStatus": body.status,
            "dedupeKey": key,
        },
    )
    return InvoiceOut.model_validate(invoice_to_api(doc, date.today()))


@router.get("/expenses", response_model=list[ExpenseOut])
def list_expenses(access: CanView, db: Db) -> list[ExpenseOut]:
    """Purchase bills and expenses confirmed from uploaded documents."""
    docs = records_repo.list_records(db, col.EXPENSES, access, order_by="date")
    return [ExpenseOut.model_validate(expense_to_api(d)) for d in docs]


@router.get("/payments", response_model=list[PaymentOut])
def list_payments(access: CanView, db: Db) -> list[PaymentOut]:
    docs = records_repo.list_records(db, col.PAYMENTS, access, order_by="date")
    return [PaymentOut.model_validate(payment_to_api(d)) for d in docs]


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(body: PaymentIn, access: CanEdit, db: Db) -> PaymentOut:
    doc = records_repo.create_record(
        db,
        col.PAYMENTS,
        access,
        {
            "date": body.date.isoformat(),
            "partyName": body.party_name,
            "direction": body.direction,
            "amountPaise": to_paise(body.amount),
            "method": body.method,
            "reference": body.reference,
            "invoiceNumber": body.invoice_number,
            "source": "manual",
        },
    )
    return PaymentOut.model_validate(payment_to_api(doc))
