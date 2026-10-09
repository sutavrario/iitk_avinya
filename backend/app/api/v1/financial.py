from datetime import date

from fastapi import APIRouter

from app.api.v1.deps import Db
from app.repositories import collections as col
from app.repositories import records as records_repo
from app.schemas.financial import FinancialSummary
from app.schemas.records import ExpenseOut, InvoiceOut, PaymentOut
from app.services.authorization import CanView
from app.services.financial_engine import compute_financial_metrics
from app.services.invoices import expense_to_api, invoice_to_api, payment_to_api

router = APIRouter(prefix="/businesses/{business_id}/financial", tags=["financial"])


@router.get("/metrics", response_model=FinancialSummary)
def get_financial_metrics(access: CanView, db: Db) -> FinancialSummary:
    today = date.today()

    invoice_docs = records_repo.list_records(db, col.INVOICES, access, order_by="issueDate")
    invoices = [InvoiceOut.model_validate(invoice_to_api(d, today)) for d in invoice_docs]

    expense_docs = records_repo.list_records(db, col.EXPENSES, access, order_by="date")
    expenses = [ExpenseOut.model_validate(expense_to_api(d)) for d in expense_docs]

    payment_docs = records_repo.list_records(db, col.PAYMENTS, access, order_by="date")
    payments = [PaymentOut.model_validate(payment_to_api(d)) for d in payment_docs]

    return compute_financial_metrics(invoices, expenses, payments, today)
