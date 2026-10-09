from datetime import datetime
from typing import Literal

from app.schemas.common import ApiModel


class KpiSummary(ApiModel):
    total_sales: float
    outstanding_receivables: float  # confirmed unpaid / partly paid
    overdue_amount: float
    cash_collected: float
    upcoming_receivables: float = 0
    supplier_payables: float = 0
    # Imported invoices whose payment status the user hasn't confirmed yet (not in outstanding).
    unconfirmed_receivables: float = 0
    unconfirmed_count: int = 0


class MonthlyFigure(ApiModel):
    month: str
    sales: float
    expenses: float


class AgingBucket(ApiModel):
    bucket: str
    amount: float


class CustomerBalance(ApiModel):
    customer_name: str
    outstanding: float
    oldest_due_days: int


class RecentDocument(ApiModel):
    id: str
    original_filename: str
    status: Literal["processing", "done", "failed"]
    uploaded_at: str
    record_type: str
    issues: list[str] = []


class ActionItem(ApiModel):
    id: str
    type: Literal["overdue", "upcoming", "data_missing", "anomaly", "recommendation"]
    priority: Literal["high", "medium", "low"]
    title: str
    description: str
    reason: str
    suggested_deadline: str | None = None
    related_record_ids: list[str] = []
    status: Literal["pending", "completed", "dismissed"] = "pending"
    is_fact: bool = True


class DashboardSummary(ApiModel):
    is_mock: bool = False
    has_data: bool
    period_label: str
    kpis: KpiSummary
    monthly: list[MonthlyFigure]
    receivables_aging: list[AgingBucket]
    top_customers: list[CustomerBalance]
    recent_documents: list[RecentDocument] = []
    action_plan: list[ActionItem] = []
