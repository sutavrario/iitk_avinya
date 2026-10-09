import { describe, expect, it } from "vitest";
import { formatAmount, rowState } from "@/lib/ingestion";
import type { ExtractedRow, ValidationIssue } from "@/lib/types";

const issue = (code: string, severity: ValidationIssue["severity"], field: string | null = null): ValidationIssue => ({
  code,
  severity,
  message: code,
  field,
  suggestedValue: null,
  relatedRecordId: null,
});

function row(issues: ValidationIssue[], extra: Partial<ExtractedRow> = {}): ExtractedRow {
  return {
    id: "row00000",
    index: 0,
    raw: {},
    editedFields: [],
    excluded: false,
    allowDuplicate: false,
    confirmedRecordId: null,
    invoice: {
      invoiceNumber: "1",
      documentId: "d",
      recordType: "sales_invoice",
      counterpartyName: "A",
      invoiceDate: "2026-09-01",
      dueDate: null,
      currency: "INR",
      subtotal: null,
      tax: null,
      total: "100.00",
      paymentStatus: "unknown",
      documentPaymentStatus: null,
      paymentReferences: [],
      confidence: 1,
      fieldConfidence: {},
      issues,
      source: null,
    },
    ...extra,
  };
}

describe("rowState", () => {
  it("is ready when only warnings/info remain", () => {
    expect(rowState(row([issue("currency_assumed", "warning"), issue("payment_status_unverified", "info")]))).toBe("ready");
  });
  it("blocks rows with errors", () => {
    expect(rowState(row([issue("total_mismatch", "error", "total")]))).toBe("errors");
  });
  it("needs a decision for duplicates until the user allows it", () => {
    const dup = [issue("possible_duplicate", "warning", "invoiceNumber")];
    expect(rowState(row(dup))).toBe("duplicate");
    expect(rowState(row(dup, { allowDuplicate: true }))).toBe("ready");
    expect(rowState(row([issue("duplicate_in_file", "warning")]))).toBe("duplicate");
  });
  it("saved and skipped take precedence", () => {
    expect(rowState(row([issue("x", "error")], { confirmedRecordId: "r" }))).toBe("saved");
    expect(rowState(row([issue("x", "error")], { excluded: true }))).toBe("excluded");
  });
});

describe("formatAmount", () => {
  it("shows missing values as a dash, never ₹0", () => {
    expect(formatAmount(null, "INR")).toBe("—");
  });
  it("formats INR and keeps other currencies separate", () => {
    expect(formatAmount("123456.5", "INR")).toBe("₹1,23,456.50");
    expect(formatAmount("10", "USD")).toBe("USD 10.00");
  });
});
