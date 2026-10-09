from collections import defaultdict
from datetime import UTC, date, datetime

from app.schemas.financial import (
    CashFlow,
    DuplicatePaymentWarning,
    FinancialSummary,
    MonthlySummary,
)
from app.schemas.records import ExpenseOut, InvoiceOut, PaymentOut


def compute_financial_metrics(
    invoices: list[InvoiceOut],
    expenses: list[ExpenseOut],
    payments: list[PaymentOut],
    today: date | None = None,
) -> FinancialSummary:
    if today is None:
        today = date.today()

    summary = FinancialSummary()
    summary.calculated_at = datetime.now(UTC)

    warnings = []
    source_record_ids = []

    # Dictionaries for grouping
    monthly_income: dict[str, float] = defaultdict(float)
    monthly_expense: dict[str, float] = defaultdict(float)

    # Partial payments tracking
    received_by_invoice: dict[str, float] = defaultdict(float)
    paid_by_invoice: dict[str, float] = defaultdict(float)

    # Cash Flow and Duplicate Detection
    cash_in = 0.0
    cash_out = 0.0

    payment_fingerprints = defaultdict(list)
    for p in payments:
        source_record_ids.append(p.id)
        if not p.date:
            warnings.append(
                f"Payment {p.id} is missing a date. Cannot determine cash flow timeline."
            )
            continue

        # fingerprint: (date, amount, direction, party_name)
        fingerprint = (
            p.date,
            round(p.amount, 2),
            p.direction,
            p.party_name.lower().strip() if p.party_name else "",
        )
        payment_fingerprints[fingerprint].append(p.id)

        if p.direction == "received":
            cash_in += p.amount
            if p.invoice_number:
                received_by_invoice[p.invoice_number] += p.amount
        elif p.direction == "paid":
            cash_out += p.amount
            if p.invoice_number:
                paid_by_invoice[p.invoice_number] += p.amount

    summary.cash_flow = CashFlow(total_in=cash_in, total_out=cash_out, net=cash_in - cash_out)

    for _fp, ids in payment_fingerprints.items():
        if len(ids) > 1:
            warnings.append(f"Potential duplicate payments detected: {', '.join(ids)}")
            summary.duplicate_payments.append(
                DuplicatePaymentWarning(
                    payment_ids=ids, reason="Same date, amount, direction, and party"
                )
            )

    # Invoices (Receivables)
    outstanding_receivables = 0.0
    overdue_receivables = 0.0
    upcoming_receivables = 0.0

    for inv in invoices:
        source_record_ids.append(inv.id)
        if inv.currency and inv.currency.upper() != "INR":
            warnings.append(
                f"Invoice {inv.id} has currency {inv.currency}, expected INR. Value included as is."
            )

        if inv.status == "paid":
            balance = 0.0
        else:
            paid_amount = received_by_invoice.get(inv.invoice_number, 0.0)
            balance = max(0.0, inv.amount - paid_amount)

        if balance > 0:
            outstanding_receivables += balance
            if not inv.due_date:
                warnings.append(f"Invoice {inv.id} is outstanding but has no due date.")
                upcoming_receivables += balance  # default to upcoming if no due date
            else:
                if inv.due_date < today:
                    overdue_receivables += balance
                else:
                    upcoming_receivables += balance

        if inv.issue_date:
            month_key = inv.issue_date.strftime("%Y-%m")
            monthly_income[month_key] += inv.amount
        else:
            warnings.append(f"Invoice {inv.id} is missing issue_date.")

    # Expenses (Payables)
    supplier_payables = 0.0
    expenses_total = 0.0

    for exp in expenses:
        source_record_ids.append(exp.id)
        if exp.currency and exp.currency.upper() != "INR":
            warnings.append(
                f"Expense {exp.id} has currency {exp.currency}, expected INR. Value included as is."
            )

        expenses_total += exp.total

        if exp.payment_status == "paid":
            balance = 0.0
        else:
            paid_amount = paid_by_invoice.get(exp.invoice_number, 0.0)
            balance = max(0.0, exp.total - paid_amount)

        if balance > 0:
            supplier_payables += balance
            if not exp.due_date:
                warnings.append(f"Expense {exp.id} has an outstanding balance but no due date.")

        if exp.date:
            month_key = exp.date.strftime("%Y-%m")
            monthly_expense[month_key] += exp.total
        else:
            warnings.append(f"Expense {exp.id} is missing date.")

    summary.outstanding_receivables = outstanding_receivables
    summary.overdue_receivables = overdue_receivables
    summary.upcoming_receivables = upcoming_receivables
    summary.supplier_payables = supplier_payables
    summary.expenses_total = expenses_total

    all_months = set(monthly_income.keys()) | set(monthly_expense.keys())
    for m in sorted(all_months):
        summary.monthly_summaries.append(
            MonthlySummary(
                month=m, income=monthly_income.get(m, 0.0), expense=monthly_expense.get(m, 0.0)
            )
        )

    summary.warnings = warnings
    summary.source_record_ids = source_record_ids

    return summary
