import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Logo } from "@/components/shared/logo";

export function FullPageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="grid min-h-screen place-items-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4 text-muted-foreground">
        <Logo />
        <Loader2 className="size-5 animate-spin" aria-hidden />
        <span className="text-sm">{label}</span>
      </div>
    </div>
  );
}

export function FullPageError({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="max-w-md text-center" role="alert">
        <div className="mx-auto mb-4 grid size-12 place-items-center rounded-full bg-destructive/10 text-destructive">
          <AlertTriangle className="size-6" aria-hidden />
        </div>
        <h1 className="text-lg font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        {action && <div className="mt-6 flex justify-center gap-2">{action}</div>}
      </div>
    </div>
  );
}
