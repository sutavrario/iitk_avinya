import type { PaymentDirection, PaymentMethod } from "@/lib/types";
import type { FieldErrors } from "@/lib/validation/common";

export interface InvoiceFormValues {
  invoiceNumber: string;
  customerName: string;
  issueDate: string;
  dueDate: string;
  amount: string;
  gstAmount: string;
}

export interface PaymentFormValues {
  partyName: string;
  date: string;
  direction: PaymentDirection;
  amount: string;
  method: PaymentMethod;
  reference: string;
  invoiceNumber: string;
}

function parseAmount(raw: string): number {
  return Number(raw.replace(/[,₹\s]/g, ""));
}

function validateAmount(raw: string, label: string): string | undefined {
  if (!raw.trim()) return `Enter the ${label}.`;
  const n = parseAmount(raw);
  if (Number.isNaN(n)) return `${label[0]?.toUpperCase()}${label.slice(1)} must be a number, e.g. 12500.`;
  if (n <= 0) return `${label[0]?.toUpperCase()}${label.slice(1)} must be greater than zero.`;
  if (n > 1e10) return "That amount looks too large. Please check it.";
  if (Math.round(n * 100) !== n * 100) return "Use at most 2 decimal places (paise).";
  return undefined;
}

export function validateInvoice(v: InvoiceFormValues): FieldErrors<keyof InvoiceFormValues> {
  const e: FieldErrors<keyof InvoiceFormValues> = {};
  if (!v.invoiceNumber.trim()) e.invoiceNumber = "Enter the invoice number printed on the bill.";
  if (!v.customerName.trim()) e.customerName = "Enter the customer's name.";
  if (!v.issueDate) e.issueDate = "Choose the invoice date.";
  if (!v.dueDate) e.dueDate = "Choose when payment is due.";
  else if (v.issueDate && v.dueDate < v.issueDate) e.dueDate = "Due date can't be before the invoice date.";
  e.amount = validateAmount(v.amount, "invoice amount");
  if (v.gstAmount.trim()) {
    const gst = parseAmount(v.gstAmount);
    if (Number.isNaN(gst) || gst < 0) e.gstAmount = "GST amount must be zero or a positive number.";
    else if (!e.amount && gst >= parseAmount(v.amount)) e.gstAmount = "GST should be less than the total amount.";
  }
  return e;
}

export function validatePayment(v: PaymentFormValues): FieldErrors<keyof PaymentFormValues> {
  const e: FieldErrors<keyof PaymentFormValues> = {};
  if (!v.partyName.trim())
    e.partyName = v.direction === "received" ? "Enter who paid you." : "Enter who you paid.";
  if (!v.date) e.date = "Choose the payment date.";
  e.amount = validateAmount(v.amount, "amount");
  return e;
}

export { parseAmount };
