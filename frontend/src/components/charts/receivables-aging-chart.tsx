"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { formatINRCompact } from "@/lib/format";
import type { AgingBucket } from "@/lib/types";

const COLORS = ["var(--chart-1)", "var(--chart-5)", "var(--chart-2)", "var(--chart-4)"];

export function ReceivablesAgingChart({ data }: { data: ReadonlyArray<AgingBucket> }) {
  return (
    <div className="h-72 w-full" role="img" aria-label="Bar chart of unpaid invoices grouped by how overdue they are">
      <ResponsiveContainer>
        <BarChart data={[...data]} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="bucket" tickLine={false} axisLine={false} fontSize={12} stroke="var(--muted-foreground)" />
          <YAxis
            tickFormatter={(v: number) => formatINRCompact(v)}
            tickLine={false}
            axisLine={false}
            fontSize={12}
            width={64}
            stroke="var(--muted-foreground)"
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--muted)" }} />
          <Bar dataKey="amount" name="Outstanding" radius={[6, 6, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={d.bucket} fill={COLORS[i % COLORS.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
