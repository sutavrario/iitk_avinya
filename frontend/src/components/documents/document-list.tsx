"use client";

import { Copy, FileImage, FileSpreadsheet, FileText, Loader2, RotateCw, Trash2, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { RECORD_TYPE_LABEL, isInProgress } from "@/lib/documents";
import { formatDate, formatFileSize } from "@/lib/format";
import type { DocumentKind, UploadedDocument } from "@/lib/types";

const ICONS: Record<DocumentKind, LucideIcon> = {
  spreadsheet: FileSpreadsheet,
  pdf: FileText,
  image: FileImage,
};

interface DocumentListProps {
  documents: ReadonlyArray<UploadedDocument>;
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
  canEdit?: boolean;
}

export function DocumentList({ documents, onRemove, onRetry, canEdit = true }: DocumentListProps) {
  return (
    <ul className="divide-y rounded-xl border bg-card" aria-label="Uploaded documents">
      {documents.map((doc) => (
        <DocumentItem key={doc.id} doc={doc} onRemove={onRemove} onRetry={onRetry} canEdit={canEdit} />
      ))}
    </ul>
  );
}

function DocumentItem({
  doc,
  onRemove,
  onRetry,
  canEdit,
}: {
  doc: UploadedDocument;
  onRemove: (id: string) => void;
  onRetry: (id: string) => void;
  canEdit: boolean;
}) {
  const Icon = ICONS[doc.kind];
  const clientOnly = doc.status === "uploading" || doc.id.startsWith("tmp_");
  const busy = doc.status === "uploading" || isInProgress(doc);
  const rows = doc.extraction?.rowCount ?? 0;
  const errorRows = doc.extraction?.errorRowCount ?? 0;
  const saved = doc.confirmedCount ?? 0;
  const canDelete = canEdit && !busy && saved === 0;
  const href = `/documents/${doc.id}`;

  return (
    <li className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
      <div className="flex min-w-0 flex-1 items-start gap-4">
        <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
          <Icon className="size-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            {clientOnly ? (
              <p className="truncate text-sm font-medium">{doc.fileName}</p>
            ) : (
              <Link href={href} className="truncate text-sm font-medium hover:underline">
                {doc.fileName}
              </Link>
            )}
            <StatusBadge status={doc.status} />
            {doc.duplicateOfDocumentId && (
              <Badge variant="outline" className="gap-1">
                <Copy aria-hidden /> Uploaded before
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {formatFileSize(doc.sizeBytes)} · {formatDate(doc.uploadedAt)}
            {doc.recordType && <> · {RECORD_TYPE_LABEL[doc.recordType]}</>}
            <StatusDetail doc={doc} rows={rows} errorRows={errorRows} saved={saved} />
          </p>
          {doc.status === "uploading" && (
            <Progress value={doc.progress ?? 0} aria-label={`Uploading ${doc.fileName}`} className="max-w-xs" />
          )}
          {doc.status === "failed" && (doc.processing?.errorMessage || doc.errorMessage) && (
            <p className="text-xs text-destructive">{doc.processing?.errorMessage ?? doc.errorMessage}</p>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 pl-14 sm:pl-0">
        {isInProgress(doc) && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground" role="status">
            <Loader2 className="size-3.5 animate-spin" aria-hidden /> Reading…
          </span>
        )}
        {doc.status === "needs_mapping" && (
          <Link href={href} className={buttonVariants({ size: "sm" })}>
            Match columns
          </Link>
        )}
        {doc.status === "needs_review" && (
          <Link href={href} className={buttonVariants({ size: "sm" })}>
            Review
          </Link>
        )}
        {doc.status === "completed" && (
          <Link href={href} className={buttonVariants({ size: "sm", variant: "outline" })}>
            View
          </Link>
        )}
        {canEdit && !clientOnly && (doc.status === "failed" || doc.status === "uploaded") && (
          <Button size="sm" variant="outline" onClick={() => onRetry(doc.id)}>
            <RotateCw data-icon="inline-start" /> {doc.status === "failed" ? "Retry" : "Process"}
          </Button>
        )}
        {(canDelete || (clientOnly && doc.status === "failed")) && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => onRemove(doc.id)}
            aria-label={clientOnly ? `Dismiss ${doc.fileName}` : `Delete ${doc.fileName}`}
          >
            <Trash2 />
          </Button>
        )}
      </div>
    </li>
  );
}

function StatusDetail({ doc, rows, errorRows, saved }: { doc: UploadedDocument; rows: number; errorRows: number; saved: number }) {
  if (doc.status === "needs_review")
    return (
      <>
        {" "}
        · {rows} record{rows === 1 ? "" : "s"} found{errorRows > 0 && `, ${errorRows} need attention`}
      </>
    );
  if (doc.status === "completed") return <> · {saved} saved</>;
  if (doc.status === "needs_mapping") return <> · Tell us which column is which</>;
  if (doc.processing?.method === "ocr" && doc.processing.ocrPages > 0) return <> · read with OCR</>;
  return null;
}
