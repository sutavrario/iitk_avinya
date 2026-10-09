"use client";

import { FileUp, ReceiptIndianRupee, Receipt, Search, Wallet } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { AddInvoiceDialog } from "@/components/records/add-invoice-dialog";
import { AddPaymentDialog } from "@/components/records/add-payment-dialog";
import { EXPENSE_COLUMNS, INVOICE_COLUMNS, PAYMENT_COLUMNS } from "@/components/records/record-columns";
import { DataTable } from "@/components/shared/data-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAsyncData } from "@/hooks/use-async-data";
import { api } from "@/lib/api";
import type { InvoiceStatus } from "@/lib/types";

const STATUS_FILTERS: ReadonlyArray<{ value: InvoiceStatus | "all"; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "unpaid", label: "Unpaid" },
  { value: "overdue", label: "Overdue" },
  { value: "partially_paid", label: "Part paid" },
  { value: "paid", label: "Paid" },
  { value: "unknown", label: "Status not confirmed" },
];

export function RecordsView() {
  const business = useActiveBusiness();
  const canEdit = business.role !== "viewer";
  const invoices = useAsyncData(() => api.records.listInvoices(business.id), [business.id]);
  const payments = useAsyncData(() => api.records.listPayments(business.id), [business.id]);
  const expenses = useAsyncData(() => api.records.listExpenses(business.id), [business.id]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<InvoiceStatus | "all">("all");

  const q = query.trim().toLowerCase();

  const visibleInvoices = useMemo(
    () =>
      (invoices.data ?? []).filter(
        (i) =>
          (status === "all" || i.status === status) &&
          (!q || i.invoiceNumber.toLowerCase().includes(q) || i.customerName.toLowerCase().includes(q)),
      ),
    [invoices.data, status, q],
  );

  const visiblePayments = useMemo(
    () =>
      (payments.data ?? []).filter(
        (p) => !q || p.partyName.toLowerCase().includes(q) || (p.reference ?? "").toLowerCase().includes(q),
      ),
    [payments.data, q],
  );

  const visibleExpenses = useMemo(
    () =>
      (expenses.data ?? []).filter(
        (e) => !q || e.supplierName.toLowerCase().includes(q) || e.invoiceNumber.toLowerCase().includes(q),
      ),
    [expenses.data, q],
  );

  const filtering = Boolean(q) || status !== "all";

  const uploadAction = (
    <Link href="/documents" className={buttonVariants({ variant: "outline" })}>
      <FileUp data-icon="inline-start" /> Upload a file instead
    </Link>
  );

  return (
    <>
      <PageHeader
        title="Invoices & payments"
        description="Every bill you've raised and every payment in or out."
        actions={
          canEdit && (
            <>
              <AddPaymentDialog businessId={business.id} onCreated={(p) => payments.setData((prev) => [p, ...(prev ?? [])])} />
              <AddInvoiceDialog businessId={business.id} onCreated={(i) => invoices.setData((prev) => [i, ...(prev ?? [])])} />
            </>
          )
        }
      />

      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          type="search"
          aria-label="Search records"
          placeholder="Search by customer, party, invoice or reference"
          className="pl-8"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <Tabs defaultValue="invoices">
        <TabsList>
          <TabsTrigger value="invoices">
            Invoices {invoices.data && <span className="text-muted-foreground">({visibleInvoices.length})</span>}
          </TabsTrigger>
          <TabsTrigger value="payments">
            Payments {payments.data && <span className="text-muted-foreground">({visiblePayments.length})</span>}
          </TabsTrigger>
          <TabsTrigger value="expenses">
            Bills {expenses.data && <span className="text-muted-foreground">({visibleExpenses.length})</span>}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="invoices" className="mt-4 space-y-3">
          <Select
            items={STATUS_FILTERS.map((s) => ({ value: s.value, label: s.label }))}
            value={status}
            onValueChange={(v) => v && setStatus(v as InvoiceStatus | "all")}
          >
            <SelectTrigger aria-label="Filter by status" className="w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {invoices.status === "error" ? (
            <ErrorState message={invoices.error} onRetry={invoices.reload} />
          ) : (
            <DataTable
              caption="Invoices"
              columns={INVOICE_COLUMNS}
              rows={visibleInvoices}
              getRowKey={(r) => r.id}
              loading={invoices.status === "loading"}
              empty={
                filtering ? (
                  <EmptyState icon={Search} title="No matching invoices" description="Try a different search or status filter." />
                ) : (
                  <EmptyState
                    icon={ReceiptIndianRupee}
                    title="No invoices yet"
                    description={
                      canEdit
                        ? "Add your first invoice with the button above, or upload a sales register."
                        : "Invoices added by your team will appear here."
                    }
                    action={canEdit && uploadAction}
                  />
                )
              }
            />
          )}
        </TabsContent>

        <TabsContent value="payments" className="mt-4">
          {payments.status === "error" ? (
            <ErrorState message={payments.error} onRetry={payments.reload} />
          ) : (
            <DataTable
              caption="Payments"
              columns={PAYMENT_COLUMNS}
              rows={visiblePayments}
              getRowKey={(r) => r.id}
              loading={payments.status === "loading"}
              empty={
                filtering ? (
                  <EmptyState icon={Search} title="No matching payments" description="Try a different search." />
                ) : (
                  <EmptyState
                    icon={Wallet}
                    title="No payments yet"
                    description={
                      canEdit
                        ? "Record money received or paid, or upload a bank statement."
                        : "Payments recorded by your team will appear here."
                    }
                    action={canEdit && uploadAction}
                  />
                )
              }
            />
          )}
        </TabsContent>
        <TabsContent value="expenses" className="mt-4">
          {expenses.status === "error" ? (
            <ErrorState message={expenses.error} onRetry={expenses.reload} />
          ) : (
            <DataTable
              caption="Purchase bills and expenses"
              columns={EXPENSE_COLUMNS}
              rows={visibleExpenses}
              getRowKey={(r) => r.id}
              loading={expenses.status === "loading"}
              empty={
                <EmptyState
                  icon={Receipt}
                  title={q ? "No matching bills" : "No supplier bills yet"}
                  description={
                    q ? "Try a different search." : "Upload purchase bills on the Documents page. They appear here after you review them."
                  }
                  action={!q && canEdit && uploadAction}
                />
              }
            />
          )}
        </TabsContent>
      </Tabs>
    </>
  );
}
