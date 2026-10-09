import { FirebaseError } from "firebase/app";
import { describe, expect, it } from "vitest";
import { authErrorMessage, isUserCancellation } from "@/lib/auth/errors";
import { safeNextPath } from "@/lib/auth/redirect";
import { validateSignIn, validateSignUp } from "@/lib/validation/auth";
import { hasErrors } from "@/lib/validation/common";

describe("safeNextPath", () => {
  it("allows same-site paths", () => {
    expect(safeNextPath("/records?tab=payments")).toBe("/records?tab=payments");
  });
  it.each(["https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)", "", null, "/sign-in"])(
    "rejects %s",
    (raw) => {
      expect(safeNextPath(raw)).toBe("/dashboard");
    },
  );
});

describe("authErrorMessage", () => {
  it("does not reveal whether an email is registered", () => {
    const wrongPassword = authErrorMessage(new FirebaseError("auth/wrong-password", "x"));
    const noUser = authErrorMessage(new FirebaseError("auth/user-not-found", "x"));
    expect(wrongPassword).toBe(noUser);
  });
  it("falls back to a generic message without leaking internals", () => {
    const msg = authErrorMessage(new FirebaseError("auth/internal-error", "stack trace here"));
    expect(msg).not.toContain("stack");
  });
  it("treats closing the Google pop-up as a cancellation", () => {
    expect(isUserCancellation(new FirebaseError("auth/popup-closed-by-user", "x"))).toBe(true);
    expect(isUserCancellation(new Error("x"))).toBe(false);
  });
});

describe("auth validation", () => {
  const ok = { name: "Asha", email: "asha@example.com", password: "secret123", confirmPassword: "secret123" };
  it("accepts a valid sign-up", () => {
    expect(hasErrors(validateSignUp(ok))).toBe(false);
  });
  it("rejects weak or mismatched passwords and bad emails", () => {
    expect(validateSignUp({ ...ok, password: "short1", confirmPassword: "short1" }).password).toBeDefined();
    expect(validateSignUp({ ...ok, password: "lettersonly", confirmPassword: "lettersonly" }).password).toBeDefined();
    expect(validateSignUp({ ...ok, confirmPassword: "different1" }).confirmPassword).toBeDefined();
    expect(validateSignUp({ ...ok, email: "not-an-email" }).email).toBeDefined();
    expect(validateSignIn({ email: "", password: "" })).toMatchObject({ email: expect.any(String), password: expect.any(String) });
  });
});
