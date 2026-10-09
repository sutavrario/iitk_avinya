"use client";

import { FileSpreadsheet, FileText, ImageIcon, Inbox, Info } from "lucide-react";
import { useState } from "react";
import { ChoiceCard } from "@/components/forms/choice-card";
import { toast } from "sonner";
import { DocumentList } from "@/components/documents/document-list";
import { UploadDropzone } from "@/components/documents/upload-dropzone";
import { PageHeader } from "@/components/layout/page-header";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { FieldLegend, FieldSet } from "@/components/ui/field";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Skeleton } from "@/components/ui/skeleton";
import { useAsyncData } from "@/hooks/use-async-data";
import { usePolling } from "@/hooks/use-polling";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import { UPLOAD_LIMITS } from "@/lib/constants";
import { isInProgress } from "@/lib/documents";
import { newId } from "@/lib/id";
import type { DocumentKind, IngestionRecordType, UploadedDocument } from "@/lib/types";
import { checkFile } from "@/lib/validation/upload";

const TIPS = [
  { icon: FileSpreadsheet, title: "Sales & purchase registers", body: "Excel or CSV exports from Tally, Vyapar, Busy or your own sheets." },
  { icon: FileText, title: "Invoices & bank statements", body: "PDF invoices you issued or received, and monthly bank statements." },
  { icon: ImageIcon, title: "Photos of bills", body: "Clear, well-lit photos of handwritten or printed bills." },
];

function kindOf(name: string): DocumentKind {
  const ext = name.toLowerCase().split(".").pop() ?? "";
  if (["csv", "xlsx", "xls"].includes(ext)) return "spreadsheet";
  return ext === "pdf" ? "pdf" : "image";
}

export function DocumentsView() {
  const business = useActiveBusiness();
  const canEdit = business.role !== "viewer";
  const docs = useAsyncData(() => api.documents.list(business.id), [business.id]);
  // Client-only rows for uploads in progress or that failed before reaching the server.
  const [pending, setPending] = useState<UploadedDocument[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [recordType, setRecordType] = useState<IngestionRecordType>("sales_invoice");
  const busy = pending.some((d) => d.status === "uploading");

  // Processing runs in the background on the server; refresh while anything is in progress.
  usePolling(
    async () => docs.setData(await api.documents.list(business.id)),
    2500,
    (docs.data ?? []).some(isInProgress),
  );

  const updatePending = (id: string, patch: Partial<UploadedDocument>) =>
    setPending((list) => list.map((d) => (d.id === id ? { ...d, ...patch } : d)));

  async function handleFiles(files: File[]) {
    const batch = files.slice(0, UPLOAD_LIMITS.maxFilesPerBatch);
    const checks = batch.map(checkFile);
    const errors = checks.flatMap((c) => (c.error ? [c.error] : []));
    if (files.length > batch.length)
      errors.push(`Only the first ${UPLOAD_LIMITS.maxFilesPerBatch} files were added. Upload the rest in another batch.`);
    setRejected(errors);

    const valid = checks.filter((c) => !c.error).map((c) => c.file);
    const temps = valid.map<UploadedDocument>((file) => ({
      id: newId("tmp"),
      fileName: file.name,
      sizeBytes: file.size,
      kind: kindOf(file.name),
      status: "uploading",
      progress: 0,
      uploadedAt: new Date().toISOString(),
    }));
    setPending((list) => [...temps, ...list]);

    // Sequential uploads keep progress readable and avoid saturating slow connections.
    for (const [i, file] of valid.entries()) {
      const temp = temps[i]!;
      try {
        const saved = await api.documents.upload(business.id, file, recordType, (progress) =>
          updatePending(temp.id, { progress }),
        );
        setPending((list) => list.filter((d) => d.id !== temp.id));
        docs.setData((prev) => [saved, ...(prev ?? [])]);
        toast.success(`${file.name} uploaded. Reading it now…`);
      } catch (err) {
        updatePending(temp.id, { status: "failed", errorMessage: errorMessage(err, "Upload failed. Please try again.") });
      }
    }
  }

  async function handleRetry(id: string) {
    try {
      const updated = await api.documents.process(business.id, id, {});
      docs.setData((prev) => (prev ?? []).map((d) => (d.id === id ? updated : d)));
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't restart processing."));
    }
  }

  async function handleRemove(id: string) {
    if (id.startsWith("tmp_")) {
      setPending((list) => list.filter((d) => d.id !== id));
      return;
    }
    try {
      await api.documents.remove(business.id, id);
      docs.setData((prev) => (prev ?? []).filter((d) => d.id !== id));
      toast.success("Document deleted");
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't delete the document."));
    }
  }

  const all = [...pending, ...(docs.data ?? [])];

  return (
    <>
      <PageHeader
        title="Documents"
        description="Upload invoices, sales registers or bills. We read them, you check the results, and only then are records saved."
      />

      {canEdit && (
        <Card>
          <CardContent className="space-y-4">
            <FieldSet>
              <FieldLegend variant="label">What&apos;s in these files?</FieldLegend>
              <RadioGroup
                value={recordType}
                onValueChange={(v) => setRecordType(v as IngestionRecordType)}
                className="grid gap-3 sm:grid-cols-2"
              >
                <ChoiceCard
                  htmlFor="rt-sales"
                  title="Sales invoices"
                  description="Bills you raised. Customers owe you."
                  control={<RadioGroupItem id="rt-sales" value="sales_invoice" />}
                />
                <ChoiceCard
                  htmlFor="rt-purchase"
                  title="Purchase bills & expenses"
                  description="Bills from suppliers. You owe them."
                  control={<RadioGroupItem id="rt-purchase" value="purchase_invoice" />}
                />
              </RadioGroup>
            </FieldSet>
            <UploadDropzone onFiles={(f) => void handleFiles(f)} disabled={busy} />
            <p className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Originals are kept privately in your account. Scanned PDFs and photos are read with OCR, so always check
              the results.
            </p>
          </CardContent>
        </Card>
      )}

      {rejected.length > 0 && (
        <Alert variant="destructive" aria-live="polite">
          <AlertTitle>Some files weren&apos;t added</AlertTitle>
          <AlertDescription>
            <ul className="list-disc space-y-0.5 pl-4">
              {rejected.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <section aria-labelledby="uploads-heading" className="space-y-3">
        <h2 id="uploads-heading" className="text-lg font-semibold">
          Your uploads
        </h2>
        {docs.status === "error" && <ErrorState message={docs.error} onRetry={docs.reload} />}
        {docs.status === "loading" && <Skeleton className="h-24 w-full rounded-xl" />}
        {docs.status === "success" &&
          (all.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title="No documents yet"
              description="Upload a sales sheet, invoice or bank statement. You can add more anytime."
            />
          ) : (
            <DocumentList
              documents={all}
              onRemove={(id) => void handleRemove(id)}
              onRetry={(id) => void handleRetry(id)}
              canEdit={canEdit}
            />
          ))}
      </section>

      <section aria-labelledby="tips-heading" className="space-y-3">
        <h2 id="tips-heading" className="text-lg font-semibold">
          What can I upload?
        </h2>
        <div className="grid gap-4 md:grid-cols-3">
          {TIPS.map(({ icon: Icon, title, body }) => (
            <Card key={title} size="sm">
              <CardContent className="flex gap-3">
                <Icon className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden />
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-sm text-muted-foreground">{body}</p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </>
  );
}
