"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { AuthCard, OrDivider } from "@/components/auth/auth-card";
import { GoogleButton } from "@/components/auth/google-button";
import { useRedirectWhenSignedIn } from "@/components/auth/use-redirect-when-signed-in";
import { FormField, focusFirstInvalid } from "@/components/forms/form-field";
import { useAuth } from "@/components/providers/auth-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { authErrorMessage } from "@/lib/auth/errors";
import { hasErrors, type FieldErrors } from "@/lib/validation/common";
import { validateSignIn, type SignInValues } from "@/lib/validation/auth";

export function SignInForm() {
  const { signIn } = useAuth();
  const status = useRedirectWhenSignedIn();
  const formRef = useRef<HTMLFormElement>(null);
  const [values, setValues] = useState<SignInValues>({ email: "", password: "" });
  const [errors, setErrors] = useState<FieldErrors<keyof SignInValues>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof SignInValues, v: string) => {
    setValues((p) => ({ ...p, [k]: v }));
    if (errors[k]) setErrors((p) => ({ ...p, [k]: undefined }));
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const errs = validateSignIn(values);
    if (hasErrors(errs)) {
      setErrors(errs);
      focusFirstInvalid(formRef.current);
      return;
    }
    setBusy(true);
    try {
      await signIn(values.email.trim(), values.password);
      // Redirect happens via useRedirectWhenSignedIn once auth state updates.
    } catch (err) {
      setFormError(authErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Welcome back"
      description="Sign in to see your business dashboard."
      footer={
        <>
          New to VyaparAI?{" "}
          <Link href="/sign-up" className="font-medium text-primary underline-offset-4 hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      {formError && (
        <Alert variant="destructive" role="alert">
          <AlertDescription>{formError}</AlertDescription>
        </Alert>
      )}
      <GoogleButton onError={setFormError} disabled={busy || status === "signed-in"} />
      <OrDivider />
      <form ref={formRef} onSubmit={submit} noValidate className="space-y-4">
        <FormField id="email" label="Email" error={errors.email}>
          {(c) => (
            <Input {...c} type="email" autoComplete="email" value={values.email} onChange={(e) => set("email", e.target.value)} />
          )}
        </FormField>
        <FormField id="password" label="Password" error={errors.password}>
          {(c) => (
            <Input
              {...c}
              type="password"
              autoComplete="current-password"
              value={values.password}
              onChange={(e) => set("password", e.target.value)}
            />
          )}
        </FormField>
        <div className="flex justify-end">
          <Link href="/forgot-password" className="text-sm text-primary underline-offset-4 hover:underline">
            Forgot password?
          </Link>
        </div>
        <Button type="submit" className="h-10 w-full" disabled={busy || status === "signed-in"}>
          {busy && <Loader2 className="animate-spin" data-icon="inline-start" />}
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthCard>
  );
}
