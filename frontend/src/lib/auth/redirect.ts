/** Only allow same-site relative paths after sign-in, to prevent open redirects. */
export function safeNextPath(raw: string | null | undefined, fallback = "/dashboard"): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return fallback;
  if (raw.startsWith("/sign-in") || raw.startsWith("/sign-up")) return fallback;
  return raw;
}
