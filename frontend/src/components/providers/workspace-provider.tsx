"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import type { Business, MeResponse } from "@/lib/types";

type WorkspaceState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; me: MeResponse; business: Business | null };

interface WorkspaceContextValue {
  state: WorkspaceState;
  /** Re-fetch /me and the active business (e.g. after onboarding or editing). */
  refresh(): Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

/** Loads the signed-in user's account and their active business from the API. */
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [state, setState] = useState<WorkspaceState>({ status: "loading" });

  const load = useCallback(async () => {
    try {
      const me = await api.me.get();
      const businessId = me.user.defaultBusinessId;
      const business = businessId ? await api.businesses.get(businessId) : null;
      setState({ status: "ready", me, business });
    } catch (err) {
      setState({ status: "error", message: errorMessage(err, "We couldn't load your account.") });
    }
  }, []);

  useEffect(() => {
    // Reset on account switch so one user's data is never shown to another.
    setState({ status: "loading" });
    if (user) void load();
  }, [user?.uid, load]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(async () => {
    await load();
  }, [load]);

  return <WorkspaceContext.Provider value={{ state, refresh }}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}

/** For pages inside the app shell, where a business is guaranteed by RequireBusiness. */
export function useActiveBusiness(): Business {
  const { state } = useWorkspace();
  if (state.status !== "ready" || !state.business) {
    throw new Error("useActiveBusiness must be used inside RequireBusiness");
  }
  return state.business;
}
