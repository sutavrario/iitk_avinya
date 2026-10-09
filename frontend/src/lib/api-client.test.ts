import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const signOut = vi.fn(async () => undefined);
const getIdToken = vi.fn<(force?: boolean) => Promise<string>>(async () => "token-1");
let currentUser: { getIdToken: typeof getIdToken } | null = { getIdToken };

vi.mock("firebase/auth", () => ({ signOut: (...a: unknown[]) => signOut(...(a as [])) }));
vi.mock("@/lib/firebase", () => ({ getFirebaseAuth: () => ({ currentUser }) }));

const { apiFetch, ApiError } = await import("@/lib/api-client");

function errorResponse(status: number, code: string) {
  return new Response(JSON.stringify({ error: { code, message: `msg ${code}`, request_id: "r1" } }), { status });
}

describe("apiFetch", () => {
  beforeEach(() => {
    currentUser = { getIdToken };
    signOut.mockClear();
    getIdToken.mockClear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("sends the Firebase ID token as a bearer token", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/v1/me");
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-1");
  });

  it("refuses to call the API when nobody is signed in", async () => {
    currentUser = null;
    await expect(apiFetch("/api/v1/me")).rejects.toMatchObject({ status: 401, code: "missing_token" });
  });

  it("retries once with a refreshed token, then succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(errorResponse(401, "token_expired"))
      .mockResolvedValueOnce(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await apiFetch("/api/v1/me");
    expect(getIdToken).toHaveBeenLastCalledWith(true);
    expect(signOut).not.toHaveBeenCalled();
  });

  it("signs out immediately when the session was revoked", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => errorResponse(401, "token_revoked")));
    await expect(apiFetch("/api/v1/me")).rejects.toBeInstanceOf(ApiError);
    expect(signOut).toHaveBeenCalledOnce();
  });

  it("surfaces the server's error envelope (e.g. 404 for another business)", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => errorResponse(404, "business_not_found")));
    await expect(apiFetch("/api/v1/businesses/x")).rejects.toMatchObject({
      status: 404,
      code: "business_not_found",
      requestId: "r1",
    });
    expect(signOut).not.toHaveBeenCalled();
  });

  it("reports network failures with a friendly message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(apiFetch("/api/v1/me")).rejects.toMatchObject({ code: "network_error" });
  });

  it("handles 204 No Content", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    await expect(apiFetch("/api/v1/x", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
