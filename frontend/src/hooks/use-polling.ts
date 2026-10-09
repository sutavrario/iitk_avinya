"use client";

import { useEffect, useRef } from "react";

/** Calls `callback` every `intervalMs` while `active`, pausing when the tab is hidden. */
export function usePolling(callback: () => void | Promise<void>, intervalMs: number, active: boolean) {
  const saved = useRef(callback);
  saved.current = callback;

  useEffect(() => {
    if (!active) return;
    let timer: ReturnType<typeof setTimeout>;
    let cancelled = false;
    const tick = async () => {
      if (!document.hidden) {
        try {
          await saved.current();
        } catch {
          /* the next tick retries; errors are surfaced by the caller's own state */
        }
      }
      if (!cancelled) timer = setTimeout(tick, intervalMs);
    };
    timer = setTimeout(tick, intervalMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [intervalMs, active]);
}
