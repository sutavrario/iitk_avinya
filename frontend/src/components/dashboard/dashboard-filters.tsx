"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Filter } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";

export function DashboardFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  
  const status = searchParams.get("status") || "all";
  const customerName = searchParams.get("customer_name") || "";
  const supplierName = searchParams.get("supplier_name") || "";

  const updateParam = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "all" || !value) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
    router.push(`${pathname}?${params.toString()}`);
  };

  return (
    <div className="flex flex-wrap items-center gap-3 mb-4 bg-card p-3 rounded-xl border shadow-sm">
      <div className="flex items-center text-sm font-medium mr-1 text-muted-foreground">
        <Filter className="h-4 w-4 mr-2" />
        Filters:
      </div>
      
      <Select value={status} onValueChange={(v) => updateParam("status", v)}>
        <SelectTrigger className="w-[160px] h-9">
          <SelectValue placeholder="Record Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Statuses</SelectItem>
          <SelectItem value="unpaid">Unpaid</SelectItem>
          <SelectItem value="paid">Paid</SelectItem>
          <SelectItem value="overdue">Overdue</SelectItem>
        </SelectContent>
      </Select>

      <Input
        type="text"
        placeholder="Filter by customer..."
        className="w-[180px] h-9"
        value={customerName}
        onChange={(e) => updateParam("customer_name", e.target.value)}
      />

      <Input
        type="text"
        placeholder="Filter by supplier..."
        className="w-[180px] h-9"
        value={supplierName}
        onChange={(e) => updateParam("supplier_name", e.target.value)}
      />
    </div>
  );
}
