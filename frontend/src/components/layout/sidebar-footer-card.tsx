import { Sparkles } from "lucide-react";

export function SidebarFooterCard() {
  return (
    <div className="rounded-lg border border-dashed border-sidebar-border bg-background/60 p-3 text-xs text-muted-foreground">
      <p className="flex items-center gap-1.5 font-medium text-foreground">
        <Sparkles className="size-3.5 text-brand-accent" aria-hidden />
        Early access
      </p>
      <p className="mt-1">
        Your records are saved securely. Reading uploaded files and AI answers are coming soon.
      </p>
    </div>
  );
}
