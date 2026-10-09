import { CheckCircle2, Circle } from "lucide-react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function SetupChecklist({ hasRecords }: { hasRecords: boolean }) {
  const items = [
    { done: true, label: "Set up your business profile", href: "/settings" },
    { done: hasRecords, label: "Add your first invoice or payment", href: "/records" },
    { done: false, label: "Upload a sales sheet, invoice or statement", href: "/documents" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Getting started</CardTitle>
        <CardDescription>A few steps to get the most out of VyaparAI.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1">
          {items.map((item) => (
            <li key={item.label}>
              <Link href={item.href} className="flex items-center gap-3 rounded-md p-2 text-sm hover:bg-muted">
                {item.done ? (
                  <CheckCircle2 className="size-4 text-success" aria-hidden />
                ) : (
                  <Circle className="size-4 text-muted-foreground" aria-hidden />
                )}
                <span className={cn(item.done && "text-muted-foreground line-through")}>{item.label}</span>
                <span className="sr-only">{item.done ? "(done)" : "(to do)"}</span>
              </Link>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
