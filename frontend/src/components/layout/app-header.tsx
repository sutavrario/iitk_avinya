"use client";

import { MobileNav } from "@/components/layout/mobile-nav";
import { UserMenu } from "@/components/layout/user-menu";
import { useActiveBusiness } from "@/components/providers/workspace-provider";
import { Badge } from "@/components/ui/badge";

const ROLE_LABEL = { owner: "Owner", admin: "Admin", member: "Member", viewer: "View only" } as const;

export function AppHeader() {
  const business = useActiveBusiness();
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur sm:px-6">
      <MobileNav />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{business.businessName}</p>
        <p className="truncate text-xs text-muted-foreground">
          {business.location.city}, {business.location.state}
        </p>
      </div>
      {business.role !== "owner" && (
        <Badge variant="outline" className="hidden sm:inline-flex">
          {ROLE_LABEL[business.role]}
        </Badge>
      )}
      <UserMenu />
    </header>
  );
}
