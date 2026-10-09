import type { BusinessGoal, FinancialYearStart, LanguageCode } from "@/lib/types";

export interface Option<T extends string = string> {
  value: T;
  label: string;
  description?: string;
}

export const LANGUAGES: ReadonlyArray<Option<LanguageCode> & { nativeLabel: string }> = [
  { value: "en", label: "English", nativeLabel: "English" },
  { value: "hi", label: "Hindi", nativeLabel: "हिन्दी" },
  { value: "bn", label: "Bengali", nativeLabel: "বাংলা" },
  { value: "ta", label: "Tamil", nativeLabel: "தமிழ்" },
  { value: "te", label: "Telugu", nativeLabel: "తెలుగు" },
  { value: "mr", label: "Marathi", nativeLabel: "मराठी" },
  { value: "gu", label: "Gujarati", nativeLabel: "ગુજરાતી" },
  { value: "kn", label: "Kannada", nativeLabel: "ಕನ್ನಡ" },
  { value: "ml", label: "Malayalam", nativeLabel: "മലയാളം" },
  { value: "pa", label: "Punjabi", nativeLabel: "ਪੰਜਾਬੀ" },
];

export const INDUSTRIES: ReadonlyArray<Option> = [
  { value: "retail", label: "Retail & kirana" },
  { value: "wholesale", label: "Wholesale & distribution" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "textiles", label: "Textiles & apparel" },
  { value: "food", label: "Food & restaurants" },
  { value: "services", label: "Professional services" },
  { value: "construction", label: "Construction & hardware" },
  { value: "healthcare", label: "Pharmacy & healthcare" },
  { value: "transport", label: "Transport & logistics" },
  { value: "other", label: "Other" },
];

export const BUSINESS_TYPES: ReadonlyArray<Option> = [
  { value: "proprietorship", label: "Sole proprietorship" },
  { value: "partnership", label: "Partnership" },
  { value: "llp", label: "LLP" },
  { value: "private_limited", label: "Private limited company" },
  { value: "other", label: "Other / not sure" },
];

export const INDIAN_STATES: ReadonlyArray<string> = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat",
  "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh",
  "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan",
  "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

export const FINANCIAL_YEAR_OPTIONS: ReadonlyArray<Option<FinancialYearStart>> = [
  { value: "april", label: "April – March", description: "Standard Indian financial year" },
  { value: "january", label: "January – December", description: "Calendar year" },
];

export const PAYMENT_TERMS_OPTIONS: ReadonlyArray<Option> = [
  { value: "0", label: "Immediate / cash on delivery" },
  { value: "7", label: "Within 7 days" },
  { value: "15", label: "Within 15 days" },
  { value: "30", label: "Within 30 days" },
  { value: "45", label: "Within 45 days" },
  { value: "60", label: "Within 60 days" },
  { value: "90", label: "Within 90 days" },
];

export const BUSINESS_GOALS: ReadonlyArray<Option<BusinessGoal>> = [
  { value: "track_cash_flow", label: "Track cash flow", description: "Know what's coming in and going out" },
  { value: "collect_payments_faster", label: "Collect payments faster", description: "Follow up on overdue invoices" },
  { value: "reduce_expenses", label: "Reduce expenses", description: "Spot where money is leaking" },
  { value: "gst_compliance", label: "Stay GST-ready", description: "Keep invoices and tax data organised" },
  { value: "grow_sales", label: "Grow sales", description: "Find best customers and products" },
  { value: "manage_inventory", label: "Manage stock", description: "Avoid over- and under-stocking" },
  { value: "get_loan_ready", label: "Get loan-ready", description: "Prepare clean records for lenders" },
];

export const UPLOAD_LIMITS = {
  maxFileSizeBytes: 10 * 1024 * 1024,
  maxFilesPerBatch: 10,
  acceptedExtensions: [".csv", ".xlsx", ".xls", ".pdf", ".png", ".jpg", ".jpeg"],
} as const;
