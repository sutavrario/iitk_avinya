"use client";

import { Menu } from "lucide-react";
import { useState } from "react";
import { NavLinks } from "@/components/layout/nav-links";
import { SidebarFooterCard } from "@/components/layout/sidebar-footer-card";
import { Logo } from "@/components/shared/logo";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

export function MobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={<Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu" />}
      >
        <Menu />
      </SheetTrigger>
      <SheetContent side="left" className="w-72 bg-sidebar p-0">
        <SheetTitle className="sr-only">Navigation</SheetTitle>
        <div className="flex h-16 items-center px-5">
          <Logo href="/dashboard" />
        </div>
        <div className="flex-1 px-3">
          <NavLinks onNavigate={() => setOpen(false)} />
        </div>
        <div className="p-3">
          <SidebarFooterCard />
        </div>
      </SheetContent>
    </Sheet>
  );
}
