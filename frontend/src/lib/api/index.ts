import type { VyaparApi } from "@/lib/api/contracts";
import { httpBusinesses, httpDashboard, httpDocuments, httpMe, httpPreferences, httpRecords } from "@/lib/api/http";
import { mockCopilot } from "@/lib/api/mock/copilot";

export type * from "@/lib/api/contracts";

/** Single entry point for data access from the UI. Only the copilot is still mocked. */
export const api: VyaparApi = {
  me: httpMe,
  preferences: httpPreferences,
  businesses: httpBusinesses,
  dashboard: httpDashboard,
  records: httpRecords,
  documents: httpDocuments,
  copilot: mockCopilot,
};
