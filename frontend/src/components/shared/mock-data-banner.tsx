import { FlaskConical } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";

interface MockDataBannerProps {
  title?: string;
  children?: React.ReactNode;
  className?: string;
}

/** Must be shown wherever illustrative figures are displayed, so they are never mistaken for real data. */
export function MockDataBanner({
  title = "Sample data — not your real figures",
  children = "These numbers are illustrative only. Upload your sales sheets or add records to see your actual business.",
  className,
}: MockDataBannerProps) {
  return (
    <Alert className={cn("border-brand-accent/40 bg-brand-accent/10", className)}>
      <FlaskConical className="text-brand-accent" aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  );
}
