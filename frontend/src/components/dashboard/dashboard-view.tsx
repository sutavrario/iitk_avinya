"use client";

import { AlertCircle, ArrowUpRight, Clock, FileUp, IndianRupee, ReceiptIndianRupee, Wallet } from "lucide-react";
import Link from "next/link";
import { ChartCard } from "@/components/charts/chart-card";
import { ReceivablesAgingChart } from "@/components/charts/receivables-aging-chart";
import { SalesExpenseChart } from "@/components/charts/sales-expense-chart";
import { SetupChecklist } from "@/components/dashboard/setup-checklist";
import { TopCustomersTable } from "@/components/dashboard/top-customers-table";
import { PageHeader } from "@/components/layout/page-header";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { MockDataBanner } from "@/components/shared/mock-data-banner";
import { StatCard, StatCardSkeleton } from "@/components/shared/stat-card";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAsyncData } from "@/hooks/use-async-data";
import { api } from "@/lib/api";
import { formatINRCompact } from "@/lib/format";

export function DashboardView() {
  const business = useActiveBusiness();
  const summary = useAsyncData(() => api.dashboard.getSummary(business.id), [business.id]);
  const data = summary.data;
  const loading = summary.status === "loading";

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={data ? data.periodLabel : "Your business at a glance"}
        actions={
          <Link href="/documents" className={buttonVariants({ variant: "outline" })}>
            Upload records <ArrowUpRight data-icon="inline-end" />
          </Link>
        }
      />

      {summary.status === "error" && <ErrorState message={summary.error} onRetry={summary.reload} />}
      {data?.isMock && <MockDataBanner />}

      {data && !data.hasData ? (
        <div className="grid gap-4 xl:grid-cols-5">
          <EmptyState
            className="bg-card xl:col-span-3"
            icon={ReceiptIndianRupee}
            title="Your dashboard will fill up as you add records"
            description="Add invoices and payments, or upload a sales sheet. Sales, money owed to you and cash collected will appear here."
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Link href="/records" className={buttonVariants()}>
                  Add an invoice
                </Link>
                <Link href="/documents" className={buttonVariants({ variant: "outline" })}>
                  <FileUp data-icon="inline-start" /> Upload a file
                </Link>
              </div>
            }
          />
          <div className="xl:col-span-2">
            <SetupChecklist hasRecords={false} />
          </div>
        </div>
      ) : (
        <>
          <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {loading || !data ? (
              Array.from({ length: 4 }, (_, i) => <StatCardSkeleton key={i} />)
            ) : (
              <>
                <StatCard label="Total sales" value={formatINRCompact(data.kpis.totalSales)} hint="This financial year" icon={IndianRupee} />
                <StatCard label="Cash collected" value={formatINRCompact(data.kpis.cashCollected)} hint="Payments received" icon={Wallet} tone="success" />
                <StatCard
                  label="Customers owe you"
                  value={formatINRCompact(data.kpis.outstandingReceivables)}
                  hint={
                    data.kpis.unconfirmedCount > 0
                      ? `+ ${formatINRCompact(data.kpis.unconfirmedReceivables)} in ${data.kpis.unconfirmedCount} imported invoice${data.kpis.unconfirmedCount === 1 ? "" : "s"} with unconfirmed status`
                      : "Unpaid invoices"
                  }
                  icon={Clock}
                  tone="warning"
                />
                <StatCard label="Overdue" value={formatINRCompact(data.kpis.overdueAmount)} hint="Past due date" icon={AlertCircle} tone="danger" />
              </>
            )}
          </section>

          <div className="grid gap-4 xl:grid-cols-5">
            <ChartCard className="xl:col-span-3" title="Sales vs expenses" description="Monthly, this financial year" isMock={data?.isMock} loading={loading}>
              {data && <SalesExpenseChart data={data.monthly} />}
            </ChartCard>
            <ChartCard className="xl:col-span-2" title="Money owed to you" description="Unpaid invoices by how late they are" isMock={data?.isMock} loading={loading}>
              {data && <ReceivablesAgingChart data={data.receivablesAging} />}
            </ChartCard>
          </div>

          <div className="grid gap-4 xl:grid-cols-5">
            <Card className="xl:col-span-3">
              <CardHeader>
                <CardTitle>Who to follow up with</CardTitle>
                <CardDescription>Customers with the largest unpaid balance</CardDescription>
              </CardHeader>
              <CardContent>
                {data && data.topCustomers.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">No unpaid invoices. Nice work!</p>
                ) : (
                  <TopCustomersTable rows={data?.topCustomers ?? []} loading={loading} />
                )}
              </CardContent>
            </Card>
            <div className="xl:col-span-2">
              <SetupChecklist hasRecords={Boolean(data?.hasData)} />
            </div>
          </div>
        </>
      )}
    </>
  );
}
