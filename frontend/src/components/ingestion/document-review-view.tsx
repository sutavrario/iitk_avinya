"use client";

import { ArrowLeft, Download, Loader2, RotateCw, ScanText, Settings2 } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ColumnMappingPanel } from "@/components/ingestion/column-mapping-panel";
import { ReviewRows } from "@/components/ingestion/review-rows";
import { IssueList } from "@/components/ingestion/row-editor";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { ErrorState } from "@/components/shared/error-state";
import { StatusBadge } from "@/components/shared/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePolling } from "@/hooks/use-polling";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import { RECORD_TYPE_LABEL, isInProgress } from "@/lib/documents";
import { formatDate, formatFileSize } from "@/lib/format";
import type { ExtractedRow, ProcessRequest, UploadedDocument } from "@/lib/types";

const METHOD_LABEL: Record<string, string> = {
  spreadsheet: "Spreadsheet",
  text_layer: "PDF text",
  ocr: "OCR (scanned)",
};

export function DocumentReviewView() {
  const business = useActiveBusiness();
  const canEdit = business.role !== "viewer";
  const { documentId } = useParams<{ documentId: string }>();
  const [doc, setDoc] = useState<UploadedDocument | null>(null);
  const [rows, setRows] = useState<ExtractedRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remapping, setRemapping] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await api.documents.get(business.id, documentId);
      setDoc(d);
      setError(null);
      if (d.status === "needs_review" || d.status === "completed") {
        setRows(await api.documents.listRows(business.id, documentId));
      } else {
        setRows(null);
      }
    } catch (err) {
      setError(errorMessage(err, "Couldn't load this document."));
    }
  }, [business.id, documentId]);

  useEffect(() => {
    void load();
  }, [load]);

  usePolling(load, 2000, doc !== null && isInProgress(doc));

  async function process(request: ProcessRequest) {
    setSubmitting(true);
    try {
      setDoc(await api.documents.process(business.id, documentId, request));
      setRows(null);
      setRemapping(false);
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't start processing."));
    } finally {
      setSubmitting(false);
    }
  }

  async function download() {
    if (!doc) return;
    setDownloading(true);
    try {
      const blob = await api.documents.downloadOriginal(business.id, doc.id);
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: doc.fileName });
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't download the original."));
    } finally {
      setDownloading(false);
    }
  }

  if (error && !doc) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!doc) return <Skeleton className="h-64 w-full rounded-xl" />;

  const extraction = doc.extraction;
  const canRemap = canEdit && doc.kind === "spreadsheet" && extraction && extraction.columns.length > 0 && !(doc.confirmedCount ?? 0);
  return (
    <>
      <div className="space-y-3">
        <Link href="/documents" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" aria-hidden /> All documents
        </Link>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="truncate text-2xl font-semibold tracking-tight">{doc.fileName}</h1>
              <StatusBadge status={doc.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {doc.recordType && RECORD_TYPE_LABEL[doc.recordType]} · {formatFileSize(doc.sizeBytes)} · uploaded{" "}
              {formatDate(doc.uploadedAt)}
              {doc.processing?.method && <> · read as {METHOD_LABEL[doc.processing.method] ?? doc.processing.method}</>}
              {extraction?.sheetName && <> · sheet “{extraction.sheetName}”</>}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {canRemap && !remapping && doc.status !== "needs_mapping" && !isInProgress(doc) && (
              <Button variant="outline" onClick={() => setRemapping(true)}>
                <Settings2 data-icon="inline-start" /> Change columns
              </Button>
            )}
            <Button variant="outline" onClick={() => void download()} disabled={downloading}>
              {downloading ? <Loader2 className="animate-spin" data-icon="inline-start" /> : <Download data-icon="inline-start" />}
              Original file
            </Button>
          </div>
        </div>
      </div>

      {doc.duplicateOfDocumentId && (
        <Alert>
          <AlertTitle>You&apos;ve uploaded this exact file before</AlertTitle>
          <AlertDescription>
            <Link href={`/documents/${doc.duplicateOfDocumentId}`} className="underline">
              Open the earlier upload
            </Link>
            . Records already saved from it will be flagged as duplicates.
          </AlertDescription>
        </Alert>
      )}

      {isInProgress(doc) && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center" role="status" aria-live="polite">
            <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
            <p className="font-medium">{doc.status === "queued" ? "Waiting to start…" : "Reading your file…"}</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Scanned pages can take up to a minute each. You can leave this page; we&apos;ll keep working.
            </p>
          </CardContent>
        </Card>
      )}

      {doc.status === "failed" && (
        <Alert variant="destructive">
          <AlertTitle>We couldn&apos;t read this file</AlertTitle>
          <AlertDescription>
            <p>{doc.processing?.errorMessage ?? "Something went wrong."}</p>
            {canEdit && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => void process({})} disabled={submitting}>
                  <RotateCw data-icon="inline-start" /> Try again
                </Button>
                {doc.kind === "pdf" && (
                  <Button size="sm" variant="outline" onClick={() => void process({ forceOcr: true })} disabled={submitting}>
                    <ScanText data-icon="inline-start" /> Try again with OCR
                  </Button>
                )}
                {canRemap && (
                  <Button size="sm" variant="outline" onClick={() => setRemapping(true)}>
                    Choose columns
                  </Button>
                )}
              </div>
            )}
          </AlertDescription>
        </Alert>
      )}

      {extraction && extraction.warnings.length > 0 && !isInProgress(doc) && <IssueList issues={extraction.warnings} />}

      {extraction && canEdit && (doc.status === "needs_mapping" || remapping) && (
        <ColumnMappingPanel
          extraction={extraction}
          recordType={doc.recordType ?? "sales_invoice"}
          submitting={submitting}
          onSubmit={(r) => void process(r)}
          onCancel={remapping ? () => setRemapping(false) : undefined}
        />
      )}
      {doc.status === "needs_mapping" && !canEdit && (
        <p className="text-sm text-muted-foreground">This file is waiting for someone with edit access to match its columns.</p>
      )}

      {!remapping && (doc.status === "needs_review" || doc.status === "completed") &&
        (rows === null ? (
          <Skeleton className="h-48 w-full rounded-xl" />
        ) : (
          <ReviewRows
            businessId={business.id}
            document={doc}
            rows={rows}
            canEdit={canEdit}
            onRowsChange={(fn) => setRows((r) => (r ? fn(r) : r))}
            onConfirmed={() => void load()}
          />
        ))}

      {doc.status === "completed" && (
        <p className="text-sm text-muted-foreground">
          Saved records are in{" "}
          <Link href="/records" className={buttonVariants({ variant: "link", className: "h-auto p-0" })}>
            Invoices &amp; payments
          </Link>
          . The original file is kept as their source.
        </p>
      )}
    </>
  );
}
