import { Logo } from "@/components/shared/logo";
import { NavLinks } from "@/components/layout/nav-links";
import { SidebarFooterCard } from "@/components/layout/sidebar-footer-card";

/** Desktop sidebar. On small screens the same links render inside MobileNav. */
export function AppSidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <div className="flex h-16 items-center px-5">
        <Logo href="/dashboard" />
      </div>
      <div className="flex-1 overflow-y-auto px-3 py-2">
        <NavLinks />
      </div>
      <div className="p-3">
        <SidebarFooterCard />
      </div>
    </aside>
  );
}
