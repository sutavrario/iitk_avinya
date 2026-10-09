import { DataTable, type Column } from "@/components/shared/data-table";
import { formatINR } from "@/lib/format";
import type { CustomerBalance } from "@/lib/types";
import { cn } from "@/lib/utils";

const COLUMNS: ReadonlyArray<Column<CustomerBalance>> = [
  { key: "name", header: "Customer", cell: (r) => <span className="font-medium">{r.customerName}</span> },
  {
    key: "days",
    header: "Oldest due",
    hideOnMobile: true,
    cell: (r) => (
      <span className={cn(r.oldestDueDays > 45 && "text-destructive")}>{r.oldestDueDays} days</span>
    ),
  },
  { key: "amount", header: "Owes you", align: "right", cell: (r) => <span className="tabular-nums">{formatINR(r.outstanding)}</span> },
];

export function TopCustomersTable({ rows, loading }: { rows: ReadonlyArray<CustomerBalance>; loading?: boolean }) {
  return (
    <DataTable
      caption="Customers with the highest outstanding balance"
      columns={COLUMNS}
      rows={rows}
      loading={loading}
      getRowKey={(r) => r.customerName}
    />
  );
}
