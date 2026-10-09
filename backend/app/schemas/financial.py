from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class MonthlySummary(BaseModel):
    month: str
    income: float
    expense: float


class CashFlow(BaseModel):
    total_in: float
    total_out: float
    net: float


class DuplicatePaymentWarning(BaseModel):
    payment_ids: list[str]
    reason: str


class FinancialSummary(BaseModel):
    outstanding_receivables: float = 0.0
    overdue_receivables: float = 0.0
    upcoming_receivables: float = 0.0
    supplier_payables: float = 0.0
    expenses_total: float = 0.0
    monthly_summaries: list[MonthlySummary] = Field(default_factory=list)
    cash_flow: CashFlow = Field(default_factory=lambda: CashFlow(total_in=0, total_out=0, net=0))

    duplicate_payments: list[DuplicatePaymentWarning] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_record_ids: list[str] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))




class FilteredQueriesResponse(BaseModel):
    invoices: list[dict[str, Any]]
    payments: list[dict[str, Any]]
    expenses: list[dict[str, Any]]
