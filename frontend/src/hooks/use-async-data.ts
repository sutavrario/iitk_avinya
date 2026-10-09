"use client";

import { useCallback, useEffect, useState, type DependencyList } from "react";
import { errorMessage } from "@/lib/api-client";

export type AsyncState<T> =
  | { status: "loading"; data?: undefined; error?: undefined }
  | { status: "success"; data: T; error?: undefined }
  | { status: "error"; data?: undefined; error: string };

/** Loads data on mount, when `deps` change, and on `reload`, with explicit loading/error states. */
export function useAsyncData<T>(loader: () => Promise<T>, deps: DependencyList = []) {
  const [state, setState] = useState<AsyncState<T>>({ status: "loading" });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    loader()
      .then((data) => !cancelled && setState({ status: "success", data }))
      .catch((err: unknown) => {
        if (!cancelled) setState({ status: "error", error: errorMessage(err) });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, ...deps]);

  const reload = useCallback(() => setVersion((v) => v + 1), []);
  /** Replace the data, or derive it from the latest value (safe inside async callbacks). */
  const setData = useCallback(
    (next: T | ((prev: T | undefined) => T)) =>
      setState((prev) => ({
        status: "success",
        data: typeof next === "function" ? (next as (p: T | undefined) => T)(prev.data) : next,
      })),
    [],
  );
  return { ...state, reload, setData };
}
