import type { Metadata } from "next";
import { RequireAuth } from "@/components/auth/guards";
import { WorkspaceProvider } from "@/components/providers/workspace-provider";

export const metadata: Metadata = { title: "Set up your business" };

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <WorkspaceProvider>{children}</WorkspaceProvider>
    </RequireAuth>
  );
}
