import { apiFetch, apiFetchBlob, apiUpload } from "@/lib/api-client";
import type { BusinessApi, CopilotApi, DashboardApi, DocumentsApi, MeApi, PreferencesApi, RecordsApi } from "@/lib/api/contracts";
import type {
  Business,
  ConfirmResponse,
  Expense,
  ExtractedRow,
  DashboardSummary,
  Invoice,
  MeResponse,
  Payment,
  UploadedDocument,
  UserPreferences,
} from "@/lib/types";

const biz = (businessId: string) => `/api/v1/businesses/${encodeURIComponent(businessId)}`;

export const httpMe: MeApi = {
  get: () => apiFetch<MeResponse>("/api/v1/me"),
};

export const httpPreferences: PreferencesApi = {
  get: () => apiFetch<UserPreferences>("/api/v1/me/preferences"),
  save: (prefs) => apiFetch<UserPreferences>("/api/v1/me/preferences", { method: "PUT", body: prefs }),
};

export const httpBusinesses: BusinessApi = {
  create: (profile) => apiFetch<Business>("/api/v1/businesses", { method: "POST", body: profile }),
  get: (id) => apiFetch<Business>(biz(id)),
  update: (id, profile) => apiFetch<Business>(biz(id), { method: "PUT", body: profile }),
};

export const httpDashboard: DashboardApi = {
  getSummary: (id, params) => {
    let url = `${biz(id)}/dashboard`;
    if (params) {
      const sp = new URLSearchParams();
      if (params.status) sp.set("status", params.status);
      if (params.customer_name) sp.set("customer_name", params.customer_name);
      if (params.supplier_name) sp.set("supplier_name", params.supplier_name);
      if (params.start_date) sp.set("start_date", params.start_date);
      if (params.end_date) sp.set("end_date", params.end_date);
      if (sp.toString()) url += `?${sp.toString()}`;
    }
    return apiFetch<DashboardSummary>(url);
  },
};

export const httpRecords: RecordsApi = {
  listInvoices: (id) => apiFetch<Invoice[]>(`${biz(id)}/invoices`),
  listPayments: (id) => apiFetch<Payment[]>(`${biz(id)}/payments`),
  listExpenses: (id) => apiFetch<Expense[]>(`${biz(id)}/expenses`),
  createInvoice: (id, input) => apiFetch<Invoice>(`${biz(id)}/invoices`, { method: "POST", body: input }),
  createPayment: (id, input) => apiFetch<Payment>(`${biz(id)}/payments`, { method: "POST", body: input }),
};

const doc = (id: string, documentId: string) => `${biz(id)}/documents/${encodeURIComponent(documentId)}`;

export const httpDocuments: DocumentsApi = {
  list: (id) => apiFetch<UploadedDocument[]>(`${biz(id)}/documents`),
  get: (id, documentId) => apiFetch<UploadedDocument>(doc(id, documentId)),
  upload: (id, file, recordType, onProgress) => {
    const form = new FormData();
    form.append("file", file);
    form.append("recordType", recordType);
    return apiUpload<UploadedDocument>(`${biz(id)}/documents`, form, onProgress);
  },
  process: (id, documentId, request) =>
    apiFetch<UploadedDocument>(`${doc(id, documentId)}/process`, { method: "POST", body: request }),
  listRows: (id, documentId) => apiFetch<ExtractedRow[]>(`${doc(id, documentId)}/rows`),
  updateRow: (id, documentId, rowId, update) =>
    apiFetch<ExtractedRow>(`${doc(id, documentId)}/rows/${encodeURIComponent(rowId)}`, { method: "PATCH", body: update }),
  confirm: (id, documentId, rowIds) =>
    apiFetch<ConfirmResponse>(`${doc(id, documentId)}/confirm`, { method: "POST", body: { rowIds: rowIds ?? null } }),
  downloadOriginal: (id, documentId) => apiFetchBlob(`${doc(id, documentId)}/file`),
  remove: (id, documentId) => apiFetch<void>(doc(id, documentId), { method: "DELETE" }),
};

export const httpCopilot: CopilotApi = {
  isMock: false,
  sendMessage: (businessId, input) => {
    return apiFetch<Record<string, unknown>>(`${biz(businessId)}/copilot/ask`, {
      method: "POST",
      body: {
        question: input.message,
        conversation_id: input.conversationId,
        language: input.language,
      },
    }).then(res => {
        return {
            id: new Date().getTime().toString(),
            role: "assistant",
            content: res.answer,
            createdAt: res.timestamp || new Date().toISOString(),
            sources: res.sources,
            caveats: res.caveats,
            recommendedActions: res.recommended_actions,
            category: res.category,
            conversationId: res.conversation_id,
        };
    });
  }
};
