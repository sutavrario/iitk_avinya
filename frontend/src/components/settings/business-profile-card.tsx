"use client";

import { Pencil } from "lucide-react";
import Link from "next/link";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { BusinessGoal } from "@/lib/types";
import { BUSINESS_GOALS, BUSINESS_TYPES, FINANCIAL_YEAR_OPTIONS, INDUSTRIES, PAYMENT_TERMS_OPTIONS } from "@/lib/constants";

const labelOf = (opts: ReadonlyArray<{ value: string; label: string }>, v: string | undefined) =>
  opts.find((o) => o.value === v)?.label;

export function BusinessProfileCard() {
  const profile = useActiveBusiness();
  const canEdit = profile.role === "owner" || profile.role === "admin";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Business details</CardTitle>
        <CardDescription>Used to personalise your dashboard and reports.</CardDescription>
        {canEdit && (
          <CardAction>
            <Link href="/onboarding" className={buttonVariants({ variant: "outline", size: "sm" })}>
              <Pencil data-icon="inline-start" /> Edit
            </Link>
          </CardAction>
        )}
      </CardHeader>
      <CardContent>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            {[
              ["Business name", profile.businessName],
              ["Industry", labelOf(INDUSTRIES, profile.industry)],
              ["Business type", labelOf(BUSINESS_TYPES, profile.businessType)],
              ["Location", [profile.location.city, profile.location.state, profile.location.pincode].filter(Boolean).join(", ")],
              ["Currency", "₹ Indian Rupee (INR)"],
              ["Financial year", labelOf(FINANCIAL_YEAR_OPTIONS, profile.financialYearStart)],
              ["Payment terms", profile.paymentTermsDays == null ? undefined : labelOf(PAYMENT_TERMS_OPTIONS, String(profile.paymentTermsDays))],
              ["GSTIN", profile.gstin ?? undefined],
              ["Goals", profile.goals.map((g: BusinessGoal) => labelOf(BUSINESS_GOALS, g)).join(", ")],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-medium">{v || <span className="font-normal text-muted-foreground">Not set</span>}</dd>
              </div>
            ))}
          </dl>
      </CardContent>
    </Card>
  );
}
