"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { FullPageError, FullPageLoader } from "@/components/auth/full-page-status";
import { useAuth } from "@/components/providers/auth-provider";
import { useWorkspace } from "@/components/providers/workspace-provider";
import { Button } from "@/components/ui/button";

/**
 * Client-side route protection for UX. Real enforcement happens on the server: the API
 * rejects requests without a valid ID token, and security rules deny direct access.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "signed-out") router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
  }, [status, router, pathname]);

  if (status === "unconfigured") {
    return (
      <FullPageError
        title="Sign-in isn't set up yet"
        message="Firebase isn't configured for this app. Add the values from frontend/.env.example to frontend/.env.local and restart the dev server."
      />
    );
  }
  if (status !== "signed-in") return <FullPageLoader label="Checking your sign-in…" />;
  return <>{children}</>;
}

/** Requires a loaded workspace with a business; sends new users to onboarding. */
export function RequireBusiness({ children }: { children: ReactNode }) {
  const { state, refresh } = useWorkspace();
  const { signOut } = useAuth();
  const router = useRouter();
  const needsOnboarding = state.status === "ready" && !state.business;

  useEffect(() => {
    if (needsOnboarding) router.replace("/onboarding");
  }, [needsOnboarding, router]);

  if (state.status === "error") {
    return (
      <FullPageError
        title="We couldn't load your business"
        message={state.message}
        action={
          <>
            <Button variant="outline" onClick={() => void signOut()}>
              Sign out
            </Button>
            <Button onClick={() => void refresh()}>Try again</Button>
          </>
        }
      />
    );
  }
  if (state.status !== "ready" || !state.business) return <FullPageLoader label="Loading your business…" />;
  return <>{children}</>;
}
