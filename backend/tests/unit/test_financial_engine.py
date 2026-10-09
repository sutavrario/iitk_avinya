from datetime import UTC, date, datetime, timedelta

from app.schemas.records import ExpenseOut, InvoiceOut, PaymentOut
from app.services.financial_engine import compute_financial_metrics


from typing import Literal


def make_invoice(
    id: str,
    amount: float,
    status: Literal["paid", "unpaid", "partially_paid", "overdue", "unknown"] = "unpaid",
    due_days: int = 10,
    inv_num: str = "",
) -> InvoiceOut:
    return InvoiceOut(
        id=id,
        invoice_number=inv_num or f"INV-{id}",
        customer_name="Test Customer",
        issue_date=date.today() - timedelta(days=5),
        due_date=date.today() + timedelta(days=due_days),
        amount=amount,
        status=status,
        source="manual",
        created_at=datetime.now(UTC),
    )


def make_payment(
    id: str,
    amount: float,
    direction: Literal["received", "paid"],
    party: str = "Test",
    date_offset: int = 0,
    inv_num: str = "",
) -> PaymentOut:
    return PaymentOut(
        id=id,
        date=date.today() + timedelta(days=date_offset),
        party_name=party,
        direction=direction,
        amount=amount,
        method="bank_transfer",
        invoice_number=inv_num,
        source="manual",
        created_at=datetime.now(UTC),
    )


def make_expense(
    id: str,
    amount: float,
    status: Literal["paid", "unpaid", "partially_paid", "unknown"] = "unpaid",
    due_days: int = 10,
    inv_num: str = "",
) -> ExpenseOut:
    return ExpenseOut(
        id=id,
        invoice_number=inv_num or f"EXP-{id}",
        supplier_name="Test Supplier",
        date=date.today() - timedelta(days=5),
        due_date=date.today() + timedelta(days=due_days),
        currency="INR",
        subtotal=amount,
        tax=0,
        total=amount,
        payment_status=status,
        document_id=None,
        created_at=datetime.now(UTC),
    )


def test_partial_payments() -> None:
    # Invoice of 1000, payment of 400
    inv = make_invoice("1", 1000.0, inv_num="INV-1")
    pay = make_payment("p1", 400.0, "received", inv_num="INV-1")

    summary = compute_financial_metrics([inv], [], [pay])

    assert summary.outstanding_receivables == 600.0
    assert summary.cash_flow.total_in == 400.0
    assert summary.cash_flow.net == 400.0


def test_overdue_invoices() -> None:
    # Invoice overdue by 2 days
    inv1 = make_invoice("1", 500.0, due_days=-2)
    # Invoice not yet due
    inv2 = make_invoice("2", 300.0, due_days=5)

    summary = compute_financial_metrics([inv1, inv2], [], [])

    assert summary.overdue_receivables == 500.0
    assert summary.upcoming_receivables == 300.0
    assert summary.outstanding_receivables == 800.0


def test_duplicate_records() -> None:
    # Two identical payments
    pay1 = make_payment("p1", 200.0, "received", date_offset=-1)
    pay2 = make_payment("p2", 200.0, "received", date_offset=-1)

    summary = compute_financial_metrics([], [], [pay1, pay2])

    assert len(summary.duplicate_payments) == 1
    assert "p1" in summary.duplicate_payments[0].payment_ids
    assert "p2" in summary.duplicate_payments[0].payment_ids
    # Both are counted towards cash flow, but warned
    assert summary.cash_flow.total_in == 400.0


def test_date_boundaries_and_reconciliation_errors() -> None:
    # Invoice fully paid via status, despite no payments
    inv1 = make_invoice("1", 1000.0, status="paid", due_days=-5)

    # Expense partially paid
    exp1 = make_expense("e1", 2000.0, inv_num="EXP-1")
    pay1 = make_payment("p1", 1500.0, "paid", inv_num="EXP-1")

    summary = compute_financial_metrics([inv1], [exp1], [pay1])

    assert summary.outstanding_receivables == 0.0
    assert summary.overdue_receivables == 0.0
    assert summary.supplier_payables == 500.0
    assert summary.expenses_total == 2000.0
    assert summary.cash_flow.total_out == 1500.0
    assert summary.cash_flow.net == -1500.0


def test_missing_dates() -> None:
    inv = make_invoice("1", 1000.0)
    inv.due_date = None

    summary = compute_financial_metrics([inv], [], [])
    assert summary.outstanding_receivables == 1000.0
    assert summary.upcoming_receivables == 1000.0
    assert any("no due date" in w for w in summary.warnings)
