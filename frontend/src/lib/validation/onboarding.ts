import type { BusinessGoal, FinancialYearStart, LanguageCode } from "@/lib/types";
import { type FieldErrors, GSTIN_PATTERN, PINCODE_PATTERN } from "@/lib/validation/common";

/** Raw form state — strings as typed by the user, converted to BusinessProfile on submit. */
export interface OnboardingFormValues {
  businessName: string;
  industry: string;
  businessType: string;
  city: string;
  state: string;
  pincode: string;
  gstin: string;
  financialYearStart: FinancialYearStart;
  paymentTerms: string;
  goals: BusinessGoal[];
  preferredLanguage: LanguageCode;
}

export type OnboardingField = keyof OnboardingFormValues;

export const ONBOARDING_STEPS = [
  { id: "business", title: "Your business", fields: ["businessName", "industry", "businessType", "city", "state", "pincode", "gstin"] },
  { id: "finance", title: "Money & payments", fields: ["financialYearStart", "paymentTerms"] },
  { id: "goals", title: "Goals & language", fields: ["goals", "preferredLanguage"] },
] as const satisfies ReadonlyArray<{ id: string; title: string; fields: ReadonlyArray<OnboardingField> }>;

export const initialOnboardingValues: OnboardingFormValues = {
  businessName: "",
  industry: "",
  businessType: "",
  city: "",
  state: "",
  pincode: "",
  gstin: "",
  financialYearStart: "april",
  paymentTerms: "",
  goals: [],
  preferredLanguage: "en",
};

export function validateOnboarding(values: OnboardingFormValues): FieldErrors<OnboardingField> {
  const errors: FieldErrors<OnboardingField> = {};
  const name = values.businessName.trim();

  if (!name) errors.businessName = "Enter your business name so we can personalise your dashboard.";
  else if (name.length < 2) errors.businessName = "Business name should be at least 2 characters.";
  else if (name.length > 100) errors.businessName = "Business name should be under 100 characters.";

  if (!values.industry) errors.industry = "Choose the industry closest to your business.";
  if (!values.city.trim()) errors.city = "Enter the city or town where you operate.";
  if (!values.state) errors.state = "Choose your state or union territory.";

  // Optional fields: validate only when filled in.
  if (values.pincode && !PINCODE_PATTERN.test(values.pincode.trim()))
    errors.pincode = "PIN code should be 6 digits, e.g. 560001.";
  if (values.gstin && !GSTIN_PATTERN.test(values.gstin.trim().toUpperCase()))
    errors.gstin = "GSTIN should be 15 characters, e.g. 29ABCDE1234F1Z5.";

  return errors;
}

/** Errors limited to a single step, so users only see messages for what they can currently fix. */
export function validateStep(
  stepIndex: number,
  values: OnboardingFormValues,
): FieldErrors<OnboardingField> {
  const all = validateOnboarding(values);
  const fields: ReadonlyArray<OnboardingField> = ONBOARDING_STEPS[stepIndex]?.fields ?? [];
  return Object.fromEntries(
    Object.entries(all).filter(([k]) => fields.includes(k as OnboardingField)),
  ) as FieldErrors<OnboardingField>;
}
