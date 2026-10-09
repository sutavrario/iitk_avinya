"use client";

import { LogOut } from "lucide-react";
import Link from "next/link";
import { FullPageError, FullPageLoader } from "@/components/auth/full-page-status";
import { OnboardingForm } from "@/components/onboarding/onboarding-form";
import { useAuth } from "@/components/providers/auth-provider";
import { useWorkspace } from "@/components/providers/workspace-provider";
import { Logo } from "@/components/shared/logo";
import { Button } from "@/components/ui/button";

export default function OnboardingPage() {
  const { state, refresh } = useWorkspace();
  const { signOut } = useAuth();

  if (state.status === "loading") return <FullPageLoader />;
  if (state.status === "error") {
    return (
      <FullPageError
        title="We couldn't load your account"
        message={state.message}
        action={<Button onClick={() => void refresh()}>Try again</Button>}
      />
    );
  }

  const existing = state.business;
  return (
    <div className="min-h-screen bg-muted/40">
      <header className="border-b bg-background">
        <div className="mx-auto flex h-16 max-w-2xl items-center justify-between px-4">
          <Logo href={existing ? "/dashboard" : "/"} />
          {existing ? (
            <Link href="/settings" className="text-sm text-muted-foreground hover:text-foreground">
              Cancel
            </Link>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => void signOut()}>
              <LogOut data-icon="inline-start" /> Sign out
            </Button>
          )}
        </div>
      </header>
      <main id="main" className="mx-auto max-w-2xl px-4 py-10">
        <div className="mb-8 space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            {existing ? "Edit business details" : "Set up your business"}
          </h1>
          <p className="text-muted-foreground">
            {existing
              ? "Changes apply to your dashboard and reports right away."
              : "Takes about 2 minutes. Only business name, industry and location are required."}
          </p>
        </div>
        <OnboardingForm existing={existing} />
      </main>
    </div>
  );
}
