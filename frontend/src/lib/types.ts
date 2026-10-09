/**
 * Domain types shared across the UI and the API layer.
 * Field names are camelCase here; the HTTP client is responsible for mapping
 * to/from the backend's snake_case JSON when it is integrated.
 */

export type LanguageCode = "en" | "hi" | "bn" | "ta" | "te" | "mr" | "gu" | "kn" | "ml" | "pa";

export type CurrencyCode = "INR";

/** Month in which the financial year starts. Indian FY is April–March. */
export type FinancialYearStart = "april" | "january";

export type BusinessGoal =
  | "track_cash_flow"
  | "collect_payments_faster"
  | "reduce_expenses"
  | "gst_compliance"
  | "grow_sales"
  | "manage_inventory"
  | "get_loan_ready";

export interface BusinessLocation {
  city: string;
  state: string;
  pincode?: string;
}

export interface BusinessProfile {
  businessName: string;
  industry: string;
  businessType: string;
  location: BusinessLocation;
  currency: CurrencyCode;
  financialYearStart: FinancialYearStart;
  /** Typical days customers take to pay; null when the owner skipped the question. */
  paymentTermsDays: number | null;
  goals: BusinessGoal[];
  preferredLanguage: LanguageCode;
  gstin?: string;
}

export type BusinessRole = "owner" | "admin" | "member" | "viewer";

/** A business as returned by the API: the profile plus server-owned fields. */
export interface Business extends BusinessProfile {
  id: string;
  /** The current user's role in this business. */
  role: BusinessRole;
  createdAt: string;
  updatedAt: string;
}

export interface Membership {
  businessId: string;
  businessName: string;
  role: BusinessRole;
}

export interface UserAccount {
  uid: string;
  email: string | null;
  displayName: string | null;
  emailVerified: boolean;
  defaultBusinessId: string | null;
  preferences: UserPreferences;
}

export interface MeResponse {
  user: UserAccount;
  memberships: Membership[];
}

/** "unknown": imported from a document; the user hasn't confirmed whether it's been paid. */
export type InvoiceStatus = "paid" | "unpaid" | "partially_paid" | "overdue" | "unknown";
export type RecordSource = "manual" | "upload";

export interface Invoice {
  id: string;
  invoiceNumber: string;
  customerName: string;
  issueDate: string; // ISO date (YYYY-MM-DD)
  dueDate: string | null; // null when the document didn't say; never guessed
  amount: number; // total, inclusive of GST
  subtotal?: number | null;
  gstAmount?: number | null;
  currency?: string;
  status: InvoiceStatus;
  paymentReferences?: string[];
  source: RecordSource;
  documentId?: string | null;
  createdAt: string;
}

export interface Expense {
  id: string;
  invoiceNumber: string;
  supplierName: string;
  date: string;
  dueDate: string | null;
  currency: string;
  subtotal: number | null;
  tax: number | null;
  total: number;
  paymentStatus: Exclude<InvoiceStatus, "overdue">;
  paymentReferences: string[];
  documentId: string | null;
  createdAt: string;
}

export type PaymentDirection = "received" | "paid";
export type PaymentMethod = "upi" | "bank_transfer" | "cash" | "cheque" | "card";

export interface Payment {
  id: string;
  date: string;
  partyName: string;
  direction: PaymentDirection;
  amount: number;
  method: PaymentMethod;
  reference?: string | null;
  invoiceNumber?: string | null;
  source: RecordSource;
  createdAt: string;
}

/** Invoices can't be created as "overdue": the server derives that from dueDate. */
export type NewInvoiceInput = {
  invoiceNumber: string;
  customerName: string;
  issueDate: string;
  dueDate: string;
  amount: number;
  gstAmount?: number;
  status?: "unpaid" | "partially_paid" | "paid";
};
export type NewPaymentInput = Omit<Payment, "id" | "source" | "createdAt">;

export type DocumentKind = "spreadsheet" | "pdf" | "image";
/**
 * "uploading" exists only in the browser. Server lifecycle:
 * queued → processing → needs_mapping | needs_review → completed, or failed (retryable).
 */
export type DocumentStatus =
  | "uploading"
  | "uploaded"
  | "queued"
  | "processing"
  | "needs_mapping"
  | "needs_review"
  | "completed"
  | "failed";
export type IngestionRecordType = "sales_invoice" | "purchase_invoice";
export type PaymentStatus = "unknown" | "unpaid" | "partially_paid" | "paid";
export type ExtractableField =
  | "invoiceNumber"
  | "counterpartyName"
  | "invoiceDate"
  | "dueDate"
  | "currency"
  | "subtotal"
  | "tax"
  | "total"
  | "paymentStatus"
  | "paymentReference";

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning" | "info";
  message: string;
  field: string | null;
  suggestedValue: string | null;
  relatedRecordId: string | null;
}

export interface ProcessingInfo {
  run: number;
  attempts: number;
  errorCode: string | null;
  errorMessage: string | null;
  retryable: boolean;
  method: string | null;
  ocrPages: number;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface ExtractionInfo {
  sheetName: string | null;
  sheetNames: string[];
  columns: string[];
  sampleRows: Record<string, string>[];
  headerRowNumber: number | null;
  mapping: Partial<Record<ExtractableField, string[]>>;
  mappingConfidence: Partial<Record<ExtractableField, number>>;
  warnings: ValidationIssue[];
  rowCount: number;
  errorRowCount: number;
}

export interface UploadedDocument {
  id: string;
  fileName: string;
  sizeBytes: number;
  kind: DocumentKind;
  contentType?: string;
  status: DocumentStatus;
  recordType?: IngestionRecordType;
  uploadedAt: string; // ISO datetime
  duplicateOfDocumentId?: string | null;
  processing?: ProcessingInfo;
  extraction?: ExtractionInfo | null;
  confirmedCount?: number;
  /** Client-only: upload progress 0–100 and error for failed uploads. */
  progress?: number;
  errorMessage?: string | null;
}

export interface SourceReference {
  documentId: string;
  fileName: string;
  storagePath: string;
  method: "spreadsheet" | "text_layer" | "ocr" | "llm";
  sheetName: string | null;
  rowNumber: number | null;
  page: number | null;
  snippet: string | null;
}

/** Normalized invoice schema. Amounts are exact decimal strings; null means "not found". */
export interface NormalizedInvoice {
  invoiceNumber: string | null;
  documentId: string | null;
  recordType: IngestionRecordType;
  counterpartyName: string | null;
  invoiceDate: string | null;
  dueDate: string | null;
  currency: string | null;
  subtotal: string | null;
  tax: string | null;
  total: string | null;
  paymentStatus: PaymentStatus;
  documentPaymentStatus: string | null;
  paymentReferences: string[];
  confidence: number;
  fieldConfidence: Record<string, number>;
  issues: ValidationIssue[];
  source: SourceReference | null;
}

export interface ExtractedRow {
  id: string;
  index: number;
  invoice: NormalizedInvoice;
  raw: Record<string, string>;
  editedFields: string[];
  excluded: boolean;
  allowDuplicate: boolean;
  confirmedRecordId: string | null;
}

export interface ProcessRequest {
  recordType?: IngestionRecordType;
  columnMapping?: Partial<Record<ExtractableField, string[]>>;
  sheetName?: string | null;
  forceOcr?: boolean;
}

export interface RowUpdate {
  values?: Partial<Record<ExtractableField, string | null>>;
  paymentStatus?: PaymentStatus;
  paymentReferences?: string[];
  excluded?: boolean;
  allowDuplicate?: boolean;
}

export interface ConfirmResponse {
  results: {
    rowId: string;
    outcome: "created" | "already_confirmed" | "duplicate" | "has_errors" | "excluded";
    recordId: string | null;
    message: string | null;
  }[];
  created: number;
  documentStatus: DocumentStatus;
}

export interface KpiSummary {
  totalSales: number;
  outstandingReceivables: number;
  overdueAmount: number;
  cashCollected: number;
  upcomingReceivables: number;
  supplierPayables: number;
  /** Imported invoices whose payment status hasn't been confirmed (not included above). */
  unconfirmedReceivables: number;
  unconfirmedCount: number;
}

export interface MonthlyFigure {
  month: string; // e.g. "Apr"
  sales: number;
  expenses: number;
}

export interface AgingBucket {
  bucket: string; // e.g. "0–30 days"
  amount: number;
}

export interface CustomerBalance {
  customerName: string;
  outstanding: number;
  oldestDueDays: number;
}

export interface RecentDocument {
  id: string;
  originalFilename: string;
  status: "processing" | "done" | "failed";
  uploadedAt: string;
  recordType: string;
  issues: string[];
}

export interface ActionItem {
  id: string;
  type: "overdue" | "upcoming" | "data_missing" | "anomaly" | "recommendation";
  priority: "high" | "medium" | "low";
  title: string;
  description: string;
  reason: string;
  suggestedDeadline: string | null;
  relatedRecordIds: string[];
  status: "pending" | "completed" | "dismissed";
  isFact: boolean;
}

export interface DashboardSummary {
  /** True only for illustrative data. The API always returns false. */
  isMock: boolean;
  /** False when the business has no invoices or payments yet. */
  hasData: boolean;
  periodLabel: string;
  kpis: KpiSummary;
  monthly: MonthlyFigure[];
  receivablesAging: AgingBucket[];
  topCustomers: CustomerBalance[];
  recentDocuments: RecentDocument[];
  actionPlan: ActionItem[];
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  /** True when the reply is a canned demo response, not generated by the AI. */
  isMock?: boolean;
  sources?: Record<string, unknown>[];
  caveats?: string[];
  recommendedActions?: string[];
  category?: string;
  conversationId?: string;
}

export interface UserPreferences {
  interfaceLanguage: LanguageCode;
  copilotLanguage: LanguageCode;
  /** Translate copilot answers into copilotLanguage even if the question was in English. */
  alwaysTranslateReplies: boolean;
  showOriginalAlongsideTranslation: boolean;
  numberFormat: "indian" | "international";
}
