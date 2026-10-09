from datetime import date
from typing import Any

from app.repositories.money import from_paise


def effective_status(stored: str, due_date: date | None, today: date) -> str:
    """Overdue is derived, not stored, so it stays correct as time passes.

    Only invoices the user has confirmed as unpaid/partly paid can become overdue; "unknown"
    stays unknown, and an invoice without a due date is never assumed overdue.
    """
    if stored in ("unpaid", "partially_paid") and due_date is not None and due_date < today:
        return "overdue"
    return stored


def _opt_money(paise: int | None) -> float | None:
    return None if paise is None else from_paise(paise)


def invoice_to_api(doc: dict[str, Any], today: date) -> dict[str, Any]:
    due = date.fromisoformat(doc["dueDate"]) if doc.get("dueDate") else None
    return {
        "id": doc["id"],
        "invoiceNumber": doc["invoiceNumber"],
        "customerName": doc["customerName"],
        "issueDate": doc["issueDate"],
        "dueDate": doc.get("dueDate"),
        "amount": from_paise(doc.get("amountPaise")),
        "subtotal": _opt_money(doc.get("subtotalPaise")),
        "gstAmount": _opt_money(doc.get("gstAmountPaise")),
        "currency": doc.get("currency") or "INR",
        "status": effective_status(doc.get("status", "unpaid"), due, today),
        "paymentReferences": doc.get("paymentReferences") or [],
        "source": doc.get("source", "manual"),
        "documentId": doc.get("documentId"),
        "createdAt": doc["createdAt"],
    }


def expense_to_api(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["id"],
        "invoiceNumber": doc["invoiceNumber"],
        "supplierName": doc["supplierName"],
        "date": doc["date"],
        "dueDate": doc.get("dueDate"),
        "currency": doc.get("currency") or "INR",
        "subtotal": _opt_money(doc.get("subtotalPaise")),
        "tax": _opt_money(doc.get("taxPaise")),
        "total": from_paise(doc.get("totalPaise")),
        "paymentStatus": doc.get("paymentStatus", "unknown"),
        "paymentReferences": doc.get("paymentReferences") or [],
        "documentId": doc.get("documentId"),
        "createdAt": doc["createdAt"],
    }


def payment_to_api(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["id"],
        "date": doc["date"],
        "partyName": doc["partyName"],
        "direction": doc["direction"],
        "amount": from_paise(doc.get("amountPaise")),
        "method": doc["method"],
        "reference": doc.get("reference"),
        "invoiceNumber": doc.get("invoiceNumber"),
        "source": doc.get("source", "manual"),
        "createdAt": doc["createdAt"],
    }
