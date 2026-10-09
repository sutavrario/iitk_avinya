/**
 * Contracts the UI depends on. Business-scoped calls take the businessId of the active
 * workspace; the backend re-checks the caller's membership on every request.
 */
import type {
  Business,
  BusinessProfile,
  ChatMessage,
  DashboardSummary,
  ConfirmResponse,
  Expense,
  ExtractedRow,
  IngestionRecordType,
  Invoice,
  LanguageCode,
  MeResponse,
  NewInvoiceInput,
  NewPaymentInput,
  Payment,
  ProcessRequest,
  RowUpdate,
  UploadedDocument,
  UserPreferences,
} from "@/lib/types";

export interface MeApi {
  get(): Promise<MeResponse>;
}

export interface PreferencesApi {
  get(): Promise<UserPreferences>;
  save(prefs: UserPreferences): Promise<UserPreferences>;
}

export interface BusinessApi {
  create(profile: BusinessProfile): Promise<Business>;
  get(businessId: string): Promise<Business>;
  update(businessId: string, profile: BusinessProfile): Promise<Business>;
}

export interface DashboardApi {
  getSummary(businessId: string, params?: { status?: string; customer_name?: string; supplier_name?: string; start_date?: string; end_date?: string }): Promise<DashboardSummary>;
}

export interface RecordsApi {
  listInvoices(businessId: string): Promise<Invoice[]>;
  listPayments(businessId: string): Promise<Payment[]>;
  listExpenses(businessId: string): Promise<Expense[]>;
  createInvoice(businessId: string, input: NewInvoiceInput): Promise<Invoice>;
  createPayment(businessId: string, input: NewPaymentInput): Promise<Payment>;
}

export interface DocumentsApi {
  list(businessId: string): Promise<UploadedDocument[]>;
  get(businessId: string, documentId: string): Promise<UploadedDocument>;
  upload(
    businessId: string,
    file: File,
    recordType: IngestionRecordType,
    onProgress?: (percent: number) => void,
  ): Promise<UploadedDocument>;
  /** Retry, or re-run with a column mapping / sheet / record type. Processing runs in the background. */
  process(businessId: string, documentId: string, request: ProcessRequest): Promise<UploadedDocument>;
  listRows(businessId: string, documentId: string): Promise<ExtractedRow[]>;
  updateRow(businessId: string, documentId: string, rowId: string, update: RowUpdate): Promise<ExtractedRow>;
  confirm(businessId: string, documentId: string, rowIds?: string[]): Promise<ConfirmResponse>;
  /** Downloads the preserved original through the API (the bucket is private). */
  downloadOriginal(businessId: string, documentId: string): Promise<Blob>;
  remove(businessId: string, documentId: string): Promise<void>;
}

export interface CopilotApi {
  /** True while replies are canned demo responses (AI not integrated yet). */
  readonly isMock: boolean;
  sendMessage(businessId: string, input: { message: string; history: ChatMessage[]; language: LanguageCode; conversationId?: string }): Promise<ChatMessage>;
}

export interface VyaparApi {
  me: MeApi;
  preferences: PreferencesApi;
  businesses: BusinessApi;
  dashboard: DashboardApi;
  records: RecordsApi;
  documents: DocumentsApi;
  copilot: CopilotApi;
}
