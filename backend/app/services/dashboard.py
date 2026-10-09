"""Dashboard figures computed from the business's own invoices and payments."""

from collections import defaultdict
from datetime import date
from typing import Any

from app.repositories.money import from_paise
from app.schemas.dashboard import (
    AgingBucket,
    CustomerBalance,
    DashboardSummary,
    KpiSummary,
    MonthlyFigure,
)
from app.services.invoices import effective_status

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def financial_year_start(today: date, fy_start: str) -> date:
    if fy_start == "january":
        return date(today.year, 1, 1)
    year = today.year if today.month >= 4 else today.year - 1
    return date(year, 4, 1)


def period_label(start: date, fy_start: str) -> str:
    if fy_start == "january":
        return f"Calendar year {start.year}"
    return f"FY {start.year}–{str(start.year + 1)[-2:]}"


def _month_keys(start: date, today: date) -> list[tuple[int, int]]:
    keys, y, m = [], start.year, start.month
    while (y, m) <= (today.year, today.month):
        keys.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return keys


def compute_summary(
    invoices: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    today: date,
    fy_start: str = "april",
) -> DashboardSummary:
    start = financial_year_start(today, fy_start)
    months = _month_keys(start, today)
    sales_by_month: dict[tuple[int, int], int] = defaultdict(int)
    expenses_by_month: dict[tuple[int, int], int] = defaultdict(int)

    total_sales = outstanding = overdue = collected = 0
    aging = {"Not yet due": 0, "1–30 days": 0, "31–60 days": 0, "60+ days": 0, "No due date": 0}
    by_customer: dict[str, dict[str, int]] = defaultdict(lambda: {"outstanding": 0, "oldest": 0})

    unconfirmed = unconfirmed_count = 0
    for inv in invoices:
        if (inv.get("currency") or "INR") != "INR":
            continue  # never mix currencies in ₹ totals
        issued = date.fromisoformat(inv["issueDate"])
        due = date.fromisoformat(inv["dueDate"]) if inv.get("dueDate") else None
        amount = int(inv.get("amountPaise", 0))
        if issued >= start:
            total_sales += amount
            sales_by_month[(issued.year, issued.month)] += amount
        status = effective_status(inv.get("status", "unpaid"), due, today)
        if status == "paid":
            continue
        if status == "unknown":
            # Not counted as owed until the user confirms it's unpaid.
            unconfirmed += amount
            unconfirmed_count += 1
            continue
        # Partial payments aren't linked to invoices yet, so the full amount counts as outstanding.
        outstanding += amount
        days_late = (today - due).days if due else None
        if days_late is not None and days_late > 0:
            overdue += amount
        bucket = (
            "No due date"
            if days_late is None
            else "Not yet due"
            if days_late <= 0
            else "1–30 days"
            if days_late <= 30
            else "31–60 days"
            if days_late <= 60
            else "60+ days"
        )
        aging[bucket] += amount
        c = by_customer[inv["customerName"]]
        c["outstanding"] += amount
        c["oldest"] = max(c["oldest"], max(days_late or 0, 0))

    for pay in payments:
        paid_on = date.fromisoformat(pay["date"])
        if paid_on < start:
            continue
        amount = int(pay.get("amountPaise", 0))
        if pay["direction"] == "received":
            collected += amount
        else:
            expenses_by_month[(paid_on.year, paid_on.month)] += amount

    top = sorted(by_customer.items(), key=lambda kv: kv[1]["outstanding"], reverse=True)[:5]
    return DashboardSummary(
        is_mock=False,
        has_data=bool(invoices or payments),
        period_label=period_label(start, fy_start),
        kpis=KpiSummary(
            total_sales=from_paise(total_sales),
            outstanding_receivables=from_paise(outstanding),
            overdue_amount=from_paise(overdue),
            cash_collected=from_paise(collected),
            unconfirmed_receivables=from_paise(unconfirmed),
            unconfirmed_count=unconfirmed_count,
        ),
        monthly=[
            MonthlyFigure(
                month=_MONTHS[m - 1],
                sales=from_paise(sales_by_month[(y, m)]),
                expenses=from_paise(expenses_by_month[(y, m)]),
            )
            for y, m in months
        ],
        receivables_aging=[
            AgingBucket(bucket=k, amount=from_paise(v))
            for k, v in aging.items()
            if k != "No due date" or v  # only show the bucket when it applies
        ],
        top_customers=[
            CustomerBalance(
                customer_name=name,
                outstanding=from_paise(v["outstanding"]),
                oldest_due_days=v["oldest"],
            )
            for name, v in top
        ],
    )
