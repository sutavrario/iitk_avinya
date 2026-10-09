"use client";

import { AlertCircle, CheckCircle2, Copy, Loader2, MinusCircle, Pencil } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { RowEditor } from "@/components/ingestion/row-editor";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { formatAmount, rowIssues, rowState, type RowState } from "@/lib/ingestion";
import type { ExtractedRow, UploadedDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

type Filter = "attention" | "ready" | "all";
const PAGE = 50;

interface Props {
  businessId: string;
  document: UploadedDocument;
  rows: ExtractedRow[];
  canEdit: boolean;
  onRowsChange: (updater: (rows: ExtractedRow[]) => ExtractedRow[]) => void;
  onConfirmed: () => void;
}

export function ReviewRows({ businessId, document, rows, canEdit, onRowsChange, onConfirmed }: Props) {
  const counts = useMemo(() => {
    const c: Record<RowState, number> = { saved: 0, excluded: 0, errors: 0, duplicate: 0, ready: 0 };
    for (const r of rows) c[rowState(r)]++;
    return c;
  }, [rows]);
  const needsAttention = counts.errors + counts.duplicate;
  const [filter, setFilter] = useState<Filter>(needsAttention ? "attention" : "all");
  const [limit, setLimit] = useState(PAGE);
  const [editing, setEditing] = useState<ExtractedRow | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const visible = rows.filter((r) => {
    const s = rowState(r);
    if (filter === "attention") return s === "errors" || s === "duplicate";
    if (filter === "ready") return s === "ready";
    return true;
  });

  function replace(updated: ExtractedRow) {
    onRowsChange((list) => list.map((r) => (r.id === updated.id ? updated : r)));
    setEditing((current) => (current?.id === updated.id ? updated : current));
  }

  async function toggleExcluded(row: ExtractedRow) {
    setTogglingId(row.id);
    try {
      replace(await api.documents.updateRow(businessId, document.id, row.id, { excluded: !row.excluded }));
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setTogglingId(null);
    }
  }

  async function confirmReady() {
    const ids = rows.filter((r) => rowState(r) === "ready").map((r) => r.id);
    setConfirming(true);
    try {
      const res = await api.documents.confirm(businessId, document.id, ids);
      const dupes = res.results.filter((r) => r.outcome === "duplicate").length;
      toast.success(`${res.created} record${res.created === 1 ? "" : "s"} saved`, {
        description: dupes ? `${dupes} skipped as duplicates of records already saved.` : undefined,
      });
      onConfirmed();
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't save the records."));
    } finally {
      setConfirming(false);
    }
  }

  const isPurchase = document.recordType === "purchase_invoice";
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm" aria-label="Review summary">
            <Stat label="Ready to save" value={counts.ready} tone="success" />
            <Stat label="Need fixing" value={counts.errors} tone="danger" />
            <Stat label="Possible duplicates" value={counts.duplicate} tone="warning" />
            <Stat label="Skipped" value={counts.excluded} />
            <Stat label="Saved" value={counts.saved} />
          </dl>
          {canEdit && (
            <Button onClick={() => void confirmReady()} disabled={confirming || counts.ready === 0}>
              {confirming && <Loader2 className="animate-spin" data-icon="inline-start" />}
              Save {counts.ready} {isPurchase ? "bill" : "invoice"}
              {counts.ready === 1 ? "" : "s"}
            </Button>
          )}
        </CardContent>
      </Card>

      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList>
          <TabsTrigger value="attention">Needs attention ({needsAttention})</TabsTrigger>
          <TabsTrigger value="ready">Ready ({counts.ready})</TabsTrigger>
          <TabsTrigger value="all">All ({rows.length})</TabsTrigger>
        </TabsList>
      </Tabs>

      {visible.length === 0 ? (
        <p className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          {filter === "attention" ? "Nothing needs your attention. 🎉" : "No records here."}
        </p>
      ) : (
        <ul className="space-y-2" aria-label="Extracted records">
          {visible.slice(0, limit).map((row) => (
            <RowCard
              key={row.id}
              row={row}
              canEdit={canEdit}
              toggling={togglingId === row.id}
              onEdit={() => setEditing(row)}
              onToggleExcluded={() => void toggleExcluded(row)}
            />
          ))}
        </ul>
      )}
      {visible.length > limit && (
        <Button variant="outline" className="w-full" onClick={() => setLimit((l) => l + PAGE)}>
          Show {Math.min(PAGE, visible.length - limit)} more
        </Button>
      )}

      <RowEditor
        businessId={businessId}
        documentId={document.id}
        row={editing}
        readOnly={!canEdit || Boolean(editing?.confirmedRecordId)}
        onClose={() => setEditing(null)}
        onSaved={replace}
      />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "success" | "danger" | "warning" }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "text-lg font-semibold tabular-nums",
          value > 0 && tone === "success" && "text-success",
          value > 0 && tone === "danger" && "text-destructive",
          value > 0 && tone === "warning" && "text-warning",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function RowCard({
  row,
  canEdit,
  toggling,
  onEdit,
  onToggleExcluded,
}: {
  row: ExtractedRow;
  canEdit: boolean;
  toggling: boolean;
  onEdit: () => void;
  onToggleExcluded: () => void;
}) {
  const inv = row.invoice;
  const state = rowState(row);
  const { errors, warnings, duplicate } = rowIssues(row);
  const where = inv.source?.rowNumber ? `Row ${inv.source.rowNumber}` : inv.source?.page ? `Page ${inv.source.page}` : `#${row.index + 1}`;

  return (
    <li
      className={cn(
        "rounded-xl border bg-card p-4",
        state === "errors" && "border-destructive/40",
        state === "duplicate" && "border-warning/50",
        state === "excluded" && "opacity-60",
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">{where}</span>
            <span className="font-medium">{inv.invoiceNumber ?? <span className="text-destructive">No number</span>}</span>
            <span className="text-muted-foreground">·</span>
            <span className="truncate">{inv.counterpartyName ?? <span className="text-destructive">No name</span>}</span>
            <StateBadge state={state} />
            {inv.paymentStatus !== "unknown" ? <StatusBadge status={inv.paymentStatus} /> : null}
          </div>
          <p className="text-sm text-muted-foreground">
            {inv.invoiceDate ? formatDate(inv.invoiceDate) : "No date"}
            {inv.dueDate && <> · due {formatDate(inv.dueDate)}</>} ·{" "}
            <span className="font-medium text-foreground tabular-nums">{formatAmount(inv.total, inv.currency)}</span>
            {inv.tax !== null && <> (tax {formatAmount(inv.tax, inv.currency)})</>}
            <span className="ml-2 text-xs">· {Math.round(inv.confidence * 100)}% confidence</span>
          </p>
          {state !== "saved" && state !== "excluded" && (errors.length > 0 || duplicate) && (
            <ul className="mt-1 space-y-0.5 text-xs">
              {errors.slice(0, 3).map((e, i) => (
                <li key={i} className="text-destructive">
                  {e.message}
                </li>
              ))}
              {duplicate && !row.allowDuplicate && <li className="text-warning">{duplicate.message}</li>}
            </ul>
          )}
          {state === "ready" && warnings.length > 0 && (
            <p className="text-xs text-warning">
              {warnings.length} thing{warnings.length === 1 ? "" : "s"} to double-check
            </p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {state !== "saved" && canEdit && (
            <Button variant="ghost" size="sm" onClick={onToggleExcluded} disabled={toggling}>
              {row.excluded ? "Include" : "Skip"}
            </Button>
          )}
          <Button variant={state === "errors" || state === "duplicate" ? "default" : "outline"} size="sm" onClick={onEdit}>
            <Pencil data-icon="inline-start" /> {state === "saved" || !canEdit ? "View" : state === "ready" ? "Check" : "Fix"}
          </Button>
        </div>
      </div>
    </li>
  );
}

function StateBadge({ state }: { state: RowState }) {
  const map = {
    saved: { label: "Saved", icon: CheckCircle2, className: "bg-success/12 text-success" },
    ready: { label: "Ready", icon: CheckCircle2, className: "bg-success/12 text-success" },
    errors: { label: "Needs fixing", icon: AlertCircle, className: "bg-destructive/10 text-destructive" },
    duplicate: { label: "Possible duplicate", icon: Copy, className: "bg-warning/15 text-warning" },
    excluded: { label: "Skipped", icon: MinusCircle, className: "bg-muted text-muted-foreground" },
  }[state];
  const Icon = map.icon;
  return (
    <Badge className={cn("gap-1 border-transparent", map.className)}>
      <Icon aria-hidden /> {map.label}
    </Badge>
  );
}
