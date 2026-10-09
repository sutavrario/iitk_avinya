import { RequireAuth, RequireBusiness } from "@/components/auth/guards";
import { AppHeader } from "@/components/layout/app-header";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { WorkspaceProvider } from "@/components/providers/workspace-provider";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <WorkspaceProvider>
        <RequireBusiness>
          <div className="flex min-h-screen">
            <AppSidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <AppHeader />
              <main id="main" className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 sm:p-6 lg:p-8">
                {children}
              </main>
            </div>
          </div>
        </RequireBusiness>
      </WorkspaceProvider>
    </RequireAuth>
  );
}
