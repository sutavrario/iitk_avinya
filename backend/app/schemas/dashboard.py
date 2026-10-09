from app.schemas.common import ApiModel


class KpiSummary(ApiModel):
    total_sales: float
    outstanding_receivables: float  # confirmed unpaid / partly paid
    overdue_amount: float
    cash_collected: float
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


class DashboardSummary(ApiModel):
    is_mock: bool = False
    has_data: bool
    period_label: str
    kpis: KpiSummary
    monthly: list[MonthlyFigure]
    receivables_aging: list[AgingBucket]
    top_customers: list[CustomerBalance]
