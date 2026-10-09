import type { Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatINR } from "@/lib/format";
import type { Expense, Invoice, Payment, PaymentMethod, RecordSource } from "@/lib/types";
import { cn } from "@/lib/utils";

const METHOD_LABELS: Record<PaymentMethod, string> = {
  upi: "UPI",
  bank_transfer: "Bank transfer",
  cash: "Cash",
  cheque: "Cheque",
  card: "Card",
};

export const PAYMENT_METHOD_OPTIONS = (Object.keys(METHOD_LABELS) as PaymentMethod[]).map((value) => ({
  value,
  label: METHOD_LABELS[value],
}));

function SourceTag({ source }: { source: RecordSource }) {
  if (source === "manual") return null;
  return (
    <Badge variant="outline" className="mt-1 flex md:mt-0 md:ml-2 md:inline-flex">
      From upload
    </Badge>
  );
}

export const INVOICE_COLUMNS: ReadonlyArray<Column<Invoice>> = [
  {
    key: "number",
    header: "Invoice",
    cell: (r) => (
      <div>
        <span className="font-medium">{r.invoiceNumber}</span>
        <span className="block text-xs text-muted-foreground md:hidden">{r.customerName}</span>
        <SourceTag source={r.source} />
      </div>
    ),
  },
  { key: "customer", header: "Customer", hideOnMobile: true, cell: (r) => r.customerName },
  { key: "issued", header: "Date", hideOnMobile: true, cell: (r) => formatDate(r.issueDate) },
  {
    key: "due",
    header: "Due",
    hideOnMobile: true,
    cell: (r) => (r.dueDate ? formatDate(r.dueDate) : <span className="text-muted-foreground">Not given</span>),
  },
  { key: "status", header: "Status", cell: (r) => <StatusBadge status={r.status} /> },
  { key: "amount", header: "Amount", align: "right", cell: (r) => <Money amount={r.amount} currency={r.currency} /> },
];

/** Amounts in other currencies are shown as-is, never converted or mixed with ₹. */
function Money({ amount, currency = "INR" }: { amount: number; currency?: string }) {
  if (currency === "INR") return <span className="tabular-nums">{formatINR(amount)}</span>;
  return (
    <span className="tabular-nums">
      {currency} {amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
    </span>
  );
}

export const EXPENSE_COLUMNS: ReadonlyArray<Column<Expense>> = [
  {
    key: "number",
    header: "Bill",
    cell: (r) => (
      <div>
        <span className="font-medium">{r.invoiceNumber}</span>
        <span className="block text-xs text-muted-foreground md:hidden">{r.supplierName}</span>
      </div>
    ),
  },
  { key: "supplier", header: "Supplier", hideOnMobile: true, cell: (r) => r.supplierName },
  { key: "date", header: "Date", hideOnMobile: true, cell: (r) => formatDate(r.date) },
  { key: "status", header: "Status", cell: (r) => <StatusBadge status={r.paymentStatus} /> },
  { key: "total", header: "Total", align: "right", cell: (r) => <Money amount={r.total} currency={r.currency} /> },
];

export const PAYMENT_COLUMNS: ReadonlyArray<Column<Payment>> = [
  { key: "date", header: "Date", cell: (r) => formatDate(r.date) },
  {
    key: "party",
    header: "Party",
    cell: (r) => (
      <div>
        <span className="font-medium">{r.partyName}</span>
        <SourceTag source={r.source} />
      </div>
    ),
  },
  { key: "method", header: "Method", hideOnMobile: true, cell: (r) => METHOD_LABELS[r.method] },
  { key: "ref", header: "Reference", hideOnMobile: true, cell: (r) => r.reference || "—" },
  {
    key: "amount",
    header: "Amount",
    align: "right",
    cell: (r) => (
      <span className={cn("tabular-nums", r.direction === "received" ? "text-success" : "text-foreground")}>
        {r.direction === "received" ? "+" : "−"}
        {formatINR(r.amount)}
      </span>
    ),
  },
];
