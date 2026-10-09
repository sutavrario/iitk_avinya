import type { DocumentStatus, UploadedDocument } from "@/lib/types";

/** Server-side states that will change on their own; poll while any document is in one. */
export const IN_PROGRESS: ReadonlySet<DocumentStatus> = new Set(["queued", "processing"]);

export function isInProgress(doc: Pick<UploadedDocument, "status">): boolean {
  return IN_PROGRESS.has(doc.status);
}

export const RECORD_TYPE_LABEL = {
  sales_invoice: "Sales invoices",
  purchase_invoice: "Purchase bills & expenses",
} as const;
