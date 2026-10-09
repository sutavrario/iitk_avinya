import type { FieldErrors } from "@/lib/validation/common";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
export const MIN_PASSWORD_LENGTH = 8;

export interface SignInValues {
  email: string;
  password: string;
}

export interface SignUpValues extends SignInValues {
  name: string;
  confirmPassword: string;
}

export function validateEmail(email: string): string | undefined {
  if (!email.trim()) return "Enter your email address.";
  if (!EMAIL.test(email.trim())) return "Enter a valid email address, e.g. name@example.com.";
  return undefined;
}

export function validateSignIn(v: SignInValues): FieldErrors<keyof SignInValues> {
  return { email: validateEmail(v.email), password: v.password ? undefined : "Enter your password." };
}

export function validateSignUp(v: SignUpValues): FieldErrors<keyof SignUpValues> {
  const e: FieldErrors<keyof SignUpValues> = { email: validateEmail(v.email) };
  if (!v.name.trim()) e.name = "Enter your name.";
  if (v.password.length < MIN_PASSWORD_LENGTH)
    e.password = `Use at least ${MIN_PASSWORD_LENGTH} characters.`;
  else if (!/[A-Za-z]/.test(v.password) || !/[0-9]/.test(v.password))
    e.password = "Use a mix of letters and numbers.";
  if (!e.password && v.confirmPassword !== v.password) e.confirmPassword = "Passwords don't match.";
  return e;
}
