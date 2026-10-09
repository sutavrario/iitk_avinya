import { describe, expect, it } from "vitest";
import { hasErrors } from "@/lib/validation/common";
import { initialOnboardingValues, validateOnboarding, validateStep } from "@/lib/validation/onboarding";
import { validateInvoice, validatePayment } from "@/lib/validation/records";

const validBusiness = { ...initialOnboardingValues, businessName: "Sharma Store", industry: "retail", city: "Pune", state: "Maharashtra" };

describe("validateOnboarding", () => {
  it("requires only name, industry, city and state", () => {
    expect(hasErrors(validateOnboarding(validBusiness))).toBe(false);
    const e = validateOnboarding(initialOnboardingValues);
    expect(Object.keys(e).sort()).toEqual(["businessName", "city", "industry", "state"]);
  });

  it("validates optional PIN and GSTIN only when provided", () => {
    expect(validateOnboarding({ ...validBusiness, pincode: "12345" }).pincode).toBeDefined();
    expect(validateOnboarding({ ...validBusiness, pincode: "411001" }).pincode).toBeUndefined();
    expect(validateOnboarding({ ...validBusiness, gstin: "BADGST" }).gstin).toBeDefined();
    expect(validateOnboarding({ ...validBusiness, gstin: "29ABCDE1234F1Z5" }).gstin).toBeUndefined();
  });

  it("scopes errors to the current step", () => {
    expect(hasErrors(validateStep(1, initialOnboardingValues))).toBe(false);
    expect(validateStep(0, initialOnboardingValues).businessName).toBeDefined();
  });
});

describe("validateInvoice", () => {
  const ok = { invoiceNumber: "INV-1", customerName: "A", issueDate: "2026-10-01", dueDate: "2026-10-31", amount: "25,000", gstAmount: "" };
  it("accepts amounts with commas and ₹", () => {
    expect(hasErrors(validateInvoice(ok))).toBe(false);
    expect(hasErrors(validateInvoice({ ...ok, amount: "₹ 1,200" }))).toBe(false);
  });
  it("rejects due date before issue date and bad amounts", () => {
    expect(validateInvoice({ ...ok, dueDate: "2026-09-01" }).dueDate).toBeDefined();
    expect(validateInvoice({ ...ok, amount: "abc" }).amount).toBeDefined();
    expect(validateInvoice({ ...ok, amount: "0" }).amount).toBeDefined();
    expect(validateInvoice({ ...ok, gstAmount: "30000" }).gstAmount).toBeDefined();
  });
});

describe("validatePayment", () => {
  it("uses direction-specific wording", () => {
    const base = { partyName: "", date: "2026-10-01", direction: "paid" as const, amount: "10", method: "upi" as const, reference: "", invoiceNumber: "" };
    expect(validatePayment(base).partyName).toBe("Enter who you paid.");
  });
});
