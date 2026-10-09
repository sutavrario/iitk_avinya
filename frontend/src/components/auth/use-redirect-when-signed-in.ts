"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { safeNextPath } from "@/lib/auth/redirect";

/** Sends already-signed-in users on to where they were going. */
export function useRedirectWhenSignedIn(fallback = "/dashboard") {
  const { status } = useAuth();
  const router = useRouter();
  const next = safeNextPath(useSearchParams().get("next"), fallback);
  useEffect(() => {
    if (status === "signed-in") router.replace(next);
  }, [status, router, next]);
  return status;
}
