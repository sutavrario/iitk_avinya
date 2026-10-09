import type { ExtractableField, ExtractedRow, IngestionRecordType, PaymentStatus, ValidationIssue } from "@/lib/types";

export const REQUIRED_FIELDS: ReadonlyArray<ExtractableField> = ["invoiceNumber", "counterpartyName", "invoiceDate", "total"];

export function fieldLabel(field: string, recordType: IngestionRecordType = "sales_invoice"): string {
  const labels: Record<string, string> = {
    invoiceNumber: recordType === "purchase_invoice" ? "Bill number" : "Invoice number",
    counterpartyName: recordType === "purchase_invoice" ? "Supplier" : "Customer",
    invoiceDate: recordType === "purchase_invoice" ? "Bill date" : "Invoice date",
    dueDate: "Due date",
    currency: "Currency",
    subtotal: "Subtotal (before tax)",
    tax: "Tax (GST)",
    total: "Total amount",
    paymentStatus: "Payment status",
    paymentReference: "Payment reference (UTR / cheque)",
    paymentReferences: "Payment references",
  };
  return labels[field] ?? field;
}

export const MAPPABLE_FIELDS: ReadonlyArray<{ field: ExtractableField; hint: string; multi?: boolean }> = [
  { field: "invoiceNumber", hint: "Used to spot duplicates" },
  { field: "counterpartyName", hint: "Who the bill is with" },
  { field: "invoiceDate", hint: "Date on the invoice" },
  { field: "dueDate", hint: "When payment is due" },
  { field: "subtotal", hint: "Taxable value" },
  { field: "tax", hint: "Pick every tax column (e.g. CGST and SGST); they're added up", multi: true },
  { field: "total", hint: "Invoice value including tax" },
  { field: "currency", hint: "Leave empty if all amounts are in ₹" },
  { field: "paymentStatus", hint: "Only used as a hint; you confirm it" },
  { field: "paymentReference", hint: "UTR, cheque or transaction number" },
];

export const PAYMENT_STATUS_OPTIONS: ReadonlyArray<{ value: PaymentStatus; label: string }> = [
  { value: "unknown", label: "Not confirmed yet" },
  { value: "unpaid", label: "Unpaid" },
  { value: "partially_paid", label: "Partly paid" },
  { value: "paid", label: "Paid" },
];

const DUPLICATE_CODES = new Set(["possible_duplicate", "duplicate_in_file"]);

export function rowIssues(row: ExtractedRow): { errors: ValidationIssue[]; warnings: ValidationIssue[]; duplicate: ValidationIssue | null } {
  const issues = row.invoice.issues;
  return {
    errors: issues.filter((i) => i.severity === "error"),
    warnings: issues.filter((i) => i.severity === "warning" && !DUPLICATE_CODES.has(i.code)),
    duplicate: issues.find((i) => DUPLICATE_CODES.has(i.code)) ?? null,
  };
}

export type RowState = "saved" | "excluded" | "errors" | "duplicate" | "ready";

export function rowState(row: ExtractedRow): RowState {
  if (row.confirmedRecordId) return "saved";
  if (row.excluded) return "excluded";
  const { errors, duplicate } = rowIssues(row);
  if (errors.length) return "errors";
  if (duplicate && !row.allowDuplicate) return "duplicate";
  return "ready";
}

/** Money strings from the API are exact decimals; format for display only. */
export function formatAmount(value: string | null, currency: string | null): string {
  if (value === null) return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  if (!currency || currency === "INR")
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(n);
  return `${currency} ${n.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}
