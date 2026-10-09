"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { APP_NAV } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";

export function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { t } = useTranslation();
  return (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {APP_NAV.map(({ href, label, icon: Icon, i18nKey }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        const displayLabel = i18nKey ? t(i18nKey, label) : label;
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
              active
                ? "bg-sidebar-accent text-sidebar-accent-foreground"
                : "text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
            )}
          >
            <Icon className="size-4 shrink-0" aria-hidden />
            {displayLabel}
          </Link>
        );
      })}
    </nav>
  );
}
