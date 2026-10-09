import { Badge } from "@/components/ui/badge";
import type { DocumentStatus, InvoiceStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type Status = InvoiceStatus | DocumentStatus;

const STYLES: Record<Status, { label: string; className: string }> = {
  paid: { label: "Paid", className: "bg-success/12 text-success" },
  unpaid: { label: "Unpaid", className: "bg-muted text-muted-foreground" },
  partially_paid: { label: "Part paid", className: "bg-warning/15 text-warning" },
  overdue: { label: "Overdue", className: "bg-destructive/10 text-destructive" },
  unknown: { label: "Status unknown", className: "bg-muted text-muted-foreground border-dashed border-border" },
  uploading: { label: "Uploading", className: "bg-primary/10 text-primary" },
  uploaded: { label: "Stored", className: "bg-primary/10 text-primary" },
  queued: { label: "Waiting", className: "bg-primary/10 text-primary" },
  processing: { label: "Reading", className: "bg-primary/10 text-primary" },
  needs_mapping: { label: "Match columns", className: "bg-warning/15 text-warning" },
  needs_review: { label: "Ready to review", className: "bg-warning/15 text-warning" },
  completed: { label: "Saved", className: "bg-success/12 text-success" },
  failed: { label: "Failed", className: "bg-destructive/10 text-destructive" },
};

export function StatusBadge({ status }: { status: Status }) {
  const s = STYLES[status];
  return <Badge className={cn("border-transparent", s.className)}>{s.label}</Badge>;
}
