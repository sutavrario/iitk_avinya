"use client";

import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { formatINRCompact } from "@/lib/format";
import type { MonthlyFigure } from "@/lib/types";

export function SalesExpenseChart({ data }: { data: ReadonlyArray<MonthlyFigure> }) {
  return (
    <div className="h-72 w-full" role="img" aria-label="Area chart of monthly sales and expenses">
      <ResponsiveContainer>
        <AreaChart data={[...data]} margin={{ left: 4, right: 8, top: 8 }}>
          <defs>
            <linearGradient id="fillSales" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.35} />
              <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="fillExpenses" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--chart-2)" stopOpacity={0.3} />
              <stop offset="95%" stopColor="var(--chart-2)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} stroke="var(--muted-foreground)" />
          <YAxis
            tickFormatter={(v: number) => formatINRCompact(v)}
            tickLine={false}
            axisLine={false}
            fontSize={12}
            width={64}
            stroke="var(--muted-foreground)"
          />
          <Tooltip content={<ChartTooltip />} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Area type="monotone" dataKey="sales" name="Sales" stroke="var(--chart-1)" strokeWidth={2} fill="url(#fillSales)" />
          <Area type="monotone" dataKey="expenses" name="Expenses" stroke="var(--chart-2)" strokeWidth={2} fill="url(#fillExpenses)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
