"use client";

import { AlertCircle, AlertTriangle, Info, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { FormField } from "@/components/forms/form-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import { PAYMENT_STATUS_OPTIONS, fieldLabel, rowIssues } from "@/lib/ingestion";
import type { ExtractableField, ExtractedRow, PaymentStatus, ValidationIssue } from "@/lib/types";
import { cn } from "@/lib/utils";

type EditableField = Exclude<ExtractableField, "paymentStatus" | "paymentReference">;
const TEXT_FIELDS: ReadonlyArray<{ field: EditableField; type: "text" | "date" | "amount" }> = [
  { field: "invoiceNumber", type: "text" },
  { field: "counterpartyName", type: "text" },
  { field: "invoiceDate", type: "date" },
  { field: "dueDate", type: "date" },
  { field: "subtotal", type: "amount" },
  { field: "tax", type: "amount" },
  { field: "total", type: "amount" },
  { field: "currency", type: "text" },
];

function initialValues(row: ExtractedRow): Record<EditableField, string> {
  const inv = row.invoice;
  return {
    invoiceNumber: inv.invoiceNumber ?? "",
    counterpartyName: inv.counterpartyName ?? "",
    invoiceDate: inv.invoiceDate ?? "",
    dueDate: inv.dueDate ?? "",
    subtotal: inv.subtotal ?? "",
    tax: inv.tax ?? "",
    total: inv.total ?? "",
    currency: inv.currency ?? "",
  };
}

interface Props {
  businessId: string;
  documentId: string;
  row: ExtractedRow | null;
  readOnly: boolean;
  onClose: () => void;
  onSaved: (row: ExtractedRow) => void;
}

export function RowEditor({ row, ...rest }: Props) {
  return (
    <Sheet open={row !== null} onOpenChange={(o) => !o && rest.onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        {row && <RowEditorBody key={`${row.id}-${row.invoice.issues.length}`} row={row} {...rest} />}
      </SheetContent>
    </Sheet>
  );
}

function RowEditorBody({ businessId, documentId, row, readOnly, onClose, onSaved }: Props & { row: ExtractedRow }) {
  const [values, setValues] = useState(() => initialValues(row));
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus>(row.invoice.paymentStatus);
  const [refs, setRefs] = useState(row.invoice.paymentReferences.join(", "));
  const [allowDuplicate, setAllowDuplicate] = useState(row.allowDuplicate);
  const [saving, setSaving] = useState(false);
  const recordType = row.invoice.recordType;
  const initial = initialValues(row);
  const { duplicate } = rowIssues(row);
  const docIssues = row.invoice.issues.filter((i) => !i.field || !TEXT_FIELDS.some((f) => f.field === i.field));

  const issuesFor = (field: string) => row.invoice.issues.filter((i) => i.field === field);

  async function save() {
    const changed = Object.fromEntries(
      TEXT_FIELDS.filter(({ field }) => values[field] !== initial[field]).map(({ field }) => [field, values[field].trim() || null]),
    );
    const newRefs = refs.split(/[,;]/).map((r) => r.trim()).filter(Boolean);
    setSaving(true);
    try {
      const updated = await api.documents.updateRow(businessId, documentId, row.id, {
        values: Object.keys(changed).length ? changed : undefined,
        paymentStatus: paymentStatus !== row.invoice.paymentStatus ? paymentStatus : undefined,
        paymentReferences: newRefs.join("|") !== row.invoice.paymentReferences.join("|") ? newRefs : undefined,
        allowDuplicate: allowDuplicate !== row.allowDuplicate ? allowDuplicate : undefined,
      });
      onSaved(updated);
      const errors = rowIssues(updated).errors.length;
      if (errors) toast.warning(`Saved. ${errors} problem${errors === 1 ? "" : "s"} still need fixing.`);
      else toast.success("Changes saved");
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't save your changes."));
    } finally {
      setSaving(false);
    }
  }

  const source = row.invoice.source;
  return (
    <>
      <SheetHeader>
        <SheetTitle>{readOnly ? "Record details" : "Check this record"}</SheetTitle>
        <SheetDescription>
          {source?.rowNumber && <>Row {source.rowNumber}{source.sheetName ? ` of "${source.sheetName}"` : ""} · </>}
          {source?.page && <>Page {source.page} · </>}
          {source?.method === "ocr" ? "Read with OCR — compare carefully with the original." : "Compare with the original if anything looks off."}
        </SheetDescription>
      </SheetHeader>

      <form
        className="space-y-5 px-4"
        onSubmit={(e) => {
          e.preventDefault();
          void save();
        }}
      >
        {docIssues.length > 0 && <IssueList issues={docIssues} />}

        {TEXT_FIELDS.map(({ field, type }) => {
          const fieldIssues = issuesFor(field);
          const raw = row.raw[field];
          const conf = row.invoice.fieldConfidence[field];
          const suggestion = fieldIssues.find((i) => i.suggestedValue)?.suggestedValue;
          const hasError = fieldIssues.some((i) => i.severity === "error");
          return (
            <div key={field} className="space-y-1.5">
              <FormField
                id={`edit-${field}`}
                label={fieldLabel(field, recordType)}
                error={hasError ? fieldIssues.filter((i) => i.severity === "error").map((i) => i.message).join(" ") : undefined}
              >
                {(c) => (
                  <Input
                    {...c}
                    type={type === "date" ? "date" : "text"}
                    inputMode={type === "amount" ? "decimal" : undefined}
                    disabled={readOnly}
                    value={values[field]}
                    placeholder={type === "amount" ? "Not found — enter if known" : undefined}
                    onChange={(e) => setValues((v) => ({ ...v, [field]: e.target.value }))}
                    className={cn(conf !== undefined && conf < 0.6 && "border-warning")}
                  />
                )}
              </FormField>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                {raw !== undefined && (
                  <span>
                    In file: <span className="font-mono text-foreground">{raw}</span>
                  </span>
                )}
                {raw === undefined && !row.editedFields.includes(field) && <span>Not found in file</span>}
                {row.editedFields.includes(field) && <Badge variant="outline">Edited</Badge>}
                {conf !== undefined && conf < 0.6 && <span className="text-warning">Low confidence</span>}
                {suggestion && !readOnly && (
                  <Button
                    type="button"
                    size="xs"
                    variant="outline"
                    onClick={() => setValues((v) => ({ ...v, [field]: suggestion }))}
                  >
                    Use {suggestion}
                  </Button>
                )}
              </div>
              {fieldIssues
                .filter((i) => i.severity !== "error")
                .map((i) => (
                  <IssueLine key={i.code} issue={i} />
                ))}
            </div>
          );
        })}

        <div className="space-y-1.5">
          <Label htmlFor="edit-payment-status">Payment status</Label>
          <Select
            items={PAYMENT_STATUS_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            value={paymentStatus}
            onValueChange={(v) => v && setPaymentStatus(v as PaymentStatus)}
            disabled={readOnly}
          >
            <SelectTrigger id="edit-payment-status" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAYMENT_STATUS_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {row.invoice.documentPaymentStatus
              ? `The document says "${row.raw.paymentStatus ?? row.invoice.documentPaymentStatus}". It may have been paid since, so confirm what's true today.`
              : "We don't guess this. Choose what's true today, or leave it unconfirmed."}
          </p>
        </div>

        <FormField id="edit-refs" label="Payment references" description="UTR, cheque or transaction numbers, separated by commas.">
          {(c) => <Input {...c} disabled={readOnly} value={refs} onChange={(e) => setRefs(e.target.value)} />}
        </FormField>

        {duplicate && !readOnly && (
          <div className="space-y-2 rounded-lg border border-warning/40 bg-warning/10 p-3">
            <IssueLine issue={duplicate} />
            <div className="flex items-center gap-2">
              <Checkbox id="allow-dup" checked={allowDuplicate} onCheckedChange={setAllowDuplicate} />
              <Label htmlFor="allow-dup" className="font-normal">
                This is a different invoice — save it anyway
              </Label>
            </div>
          </div>
        )}

        <SheetFooter className="px-0">
          {readOnly ? (
            <Button type="button" variant="outline" onClick={onClose}>
              Close
            </Button>
          ) : (
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="animate-spin" data-icon="inline-start" />}
              Save changes
            </Button>
          )}
        </SheetFooter>
      </form>
    </>
  );
}

export function IssueLine({ issue }: { issue: ValidationIssue }) {
  const Icon = issue.severity === "error" ? AlertCircle : issue.severity === "warning" ? AlertTriangle : Info;
  return (
    <p
      className={cn(
        "flex items-start gap-1.5 text-xs",
        issue.severity === "error" && "text-destructive",
        issue.severity === "warning" && "text-warning",
        issue.severity === "info" && "text-muted-foreground",
      )}
    >
      <Icon className="mt-0.5 size-3.5 shrink-0" aria-hidden />
      <span>
        <span className="sr-only">{issue.severity}: </span>
        {issue.message}
      </span>
    </p>
  );
}

export function IssueList({ issues }: { issues: ValidationIssue[] }) {
  return (
    <div className="space-y-1 rounded-lg border bg-muted/40 p-3">
      {issues.map((i, idx) => (
        <IssueLine key={`${i.code}-${idx}`} issue={i} />
      ))}
    </div>
  );
}
