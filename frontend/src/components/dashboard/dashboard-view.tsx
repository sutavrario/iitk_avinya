"use client";

import { AlertCircle, ArrowUpRight, Clock, FileUp, IndianRupee, ReceiptIndianRupee, Wallet } from "lucide-react";
import Link from "next/link";
import { ChartCard } from "@/components/charts/chart-card";
import { ReceivablesAgingChart } from "@/components/charts/receivables-aging-chart";
import { SalesExpenseChart } from "@/components/charts/sales-expense-chart";
import { SetupChecklist } from "@/components/dashboard/setup-checklist";
import { ActionPlanWidget } from "@/components/dashboard/action-plan";
import { DashboardFilters } from "@/components/dashboard/dashboard-filters";
import { RecentUploadsWidget } from "@/components/dashboard/recent-uploads";
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
import { useTranslation } from "@/lib/i18n";
import { useSearchParams } from "next/navigation";

export function DashboardView() {
  const business = useActiveBusiness();
  const searchParams = useSearchParams();
  const status = searchParams.get("status");
  
  const summary = useAsyncData(
    () => api.dashboard.getSummary(business.id, { status: status || undefined }), 
    [business.id, status]
  );
  const data = summary.data;
  const loading = summary.status === "loading";
  const { t } = useTranslation();

  return (
    <>
      <PageHeader
        title={t("nav.dashboard", "Dashboard")}
        description={data ? data.periodLabel : t("dashboard.your_business_glance", "Your business at a glance")}
        actions={
          <Link href="/documents" className={buttonVariants({ variant: "outline" })}>
            {t("dashboard.upload_records", "Upload records")} <ArrowUpRight data-icon="inline-end" />
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
          <DashboardFilters />
          
          <section aria-label="Key figures" className="grid gap-4 sm:grid-cols-3 xl:grid-cols-3">
            {loading || !data ? (
              Array.from({ length: 6 }, (_, i) => <StatCardSkeleton key={i} />)
            ) : (
              <>
                <StatCard label={t("dashboard.total_sales", "Total sales")} value={formatINRCompact(data.kpis.totalSales)} hint={t("dashboard.this_financial_year", "This financial year")} icon={IndianRupee} />
                <StatCard label={t("dashboard.cash_collected", "Cash collected")} value={formatINRCompact(data.kpis.cashCollected)} hint={t("dashboard.payments_received", "Payments received")} icon={Wallet} tone="success" />
                <StatCard label="Upcoming Receivables" value={formatINRCompact(data.kpis.upcomingReceivables)} hint="Not yet due" icon={Clock} tone="success" />
                
                <StatCard
                  label={t("dashboard.customers_owe_you", "Customers owe you")}
                  value={formatINRCompact(data.kpis.outstandingReceivables)}
                  hint={
                    data.kpis.unconfirmedCount > 0
                      ? `+ ${formatINRCompact(data.kpis.unconfirmedReceivables)} in ${data.kpis.unconfirmedCount} imported invoice${data.kpis.unconfirmedCount === 1 ? "" : "s"} with unconfirmed status`
                      : t("dashboard.unpaid_invoices", "Unpaid invoices")
                  }
                  icon={Clock}
                  tone="warning"
                />
                <StatCard label={t("dashboard.overdue", "Overdue")} value={formatINRCompact(data.kpis.overdueAmount)} hint={t("dashboard.past_due_date", "Past due date")} icon={AlertCircle} tone="danger" />
                <StatCard label="Supplier Payables" value={formatINRCompact(data.kpis.supplierPayables)} hint="Unpaid expenses" icon={AlertCircle} tone="warning" />
              </>
            )}
          </section>

          <div className="grid gap-4 xl:grid-cols-1">
             {data && <ActionPlanWidget actions={data.actionPlan} onRefresh={summary.reload} />}
          </div>

          <div className="grid gap-4 xl:grid-cols-5">
            <ChartCard className="xl:col-span-3" title={t("dashboard.sales_vs_expenses", "Sales vs expenses")} description={t("dashboard.monthly_this_financial_year", "Monthly, this financial year")} isMock={data?.isMock} loading={loading}>
              {data && <SalesExpenseChart data={data.monthly} />}
            </ChartCard>
            <ChartCard className="xl:col-span-2" title={t("dashboard.money_owed_to_you", "Money owed to you")} description={t("dashboard.unpaid_invoices_by_late", "Unpaid invoices by how late they are")} isMock={data?.isMock} loading={loading}>
              {data && <ReceivablesAgingChart data={data.receivablesAging} />}
            </ChartCard>
          </div>

          <div className="grid gap-4 xl:grid-cols-5">
            <Card className="xl:col-span-3">
              <CardHeader>
                <CardTitle>{t("dashboard.who_to_follow_up_with", "Who to follow up with")}</CardTitle>
                <CardDescription>{t("dashboard.customers_largest_unpaid", "Customers with the largest unpaid balance")}</CardDescription>
              </CardHeader>
              <CardContent>
                {data && data.topCustomers.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">{t("dashboard.no_unpaid_invoices", "No unpaid invoices. Nice work!")}</p>
                ) : (
                  <TopCustomersTable rows={data?.topCustomers ?? []} loading={loading} />
                )}
              </CardContent>
            </Card>
            <div className="xl:col-span-2 space-y-4">
              <SetupChecklist hasRecords={Boolean(data?.hasData)} />
              {data?.recentDocuments && <RecentUploadsWidget documents={data.recentDocuments} />}
            </div>
          </div>
        </>
      )}
    </>
  );
}
