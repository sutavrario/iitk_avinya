import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface ChartCardProps {
  title: string;
  description?: string;
  isMock?: boolean;
  loading?: boolean;
  className?: string;
  children: ReactNode;
}

export function ChartCard({ title, description, isMock, loading, className, children }: ChartCardProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1">
            <CardTitle>{title}</CardTitle>
            {description && <CardDescription>{description}</CardDescription>}
          </div>
          {isMock && (
            <Badge variant="outline" className="shrink-0 border-brand-accent/50">
              Sample
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>{loading ? <Skeleton className="h-64 w-full" /> : children}</CardContent>
    </Card>
  );
}
