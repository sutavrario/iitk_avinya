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
import { MIN_PASSWORD_LENGTH, validateSignUp, type SignUpValues } from "@/lib/validation/auth";

export function SignUpForm() {
  const { signUp } = useAuth();
  // New accounts continue to onboarding; the app shell would redirect there anyway.
  const status = useRedirectWhenSignedIn("/onboarding");
  const formRef = useRef<HTMLFormElement>(null);
  const [values, setValues] = useState<SignUpValues>({ name: "", email: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState<FieldErrors<keyof SignUpValues>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (k: keyof SignUpValues, v: string) => {
    setValues((p) => ({ ...p, [k]: v }));
    if (errors[k]) setErrors((p) => ({ ...p, [k]: undefined }));
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const errs = validateSignUp(values);
    if (hasErrors(errs)) {
      setErrors(errs);
      focusFirstInvalid(formRef.current);
      return;
    }
    setBusy(true);
    try {
      await signUp({ name: values.name.trim(), email: values.email.trim(), password: values.password });
    } catch (err) {
      setFormError(authErrorMessage(err));
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Create your account"
      description="Free to start. You'll set up your business next."
      footer={
        <>
          Already have an account?{" "}
          <Link href="/sign-in" className="font-medium text-primary underline-offset-4 hover:underline">
            Sign in
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
        <FormField id="name" label="Your name" error={errors.name}>
          {(c) => <Input {...c} autoComplete="name" value={values.name} onChange={(e) => set("name", e.target.value)} />}
        </FormField>
        <FormField id="email" label="Email" error={errors.email}>
          {(c) => (
            <Input {...c} type="email" autoComplete="email" value={values.email} onChange={(e) => set("email", e.target.value)} />
          )}
        </FormField>
        <FormField
          id="password"
          label="Password"
          description={`At least ${MIN_PASSWORD_LENGTH} characters, with letters and numbers.`}
          error={errors.password}
        >
          {(c) => (
            <Input
              {...c}
              type="password"
              autoComplete="new-password"
              value={values.password}
              onChange={(e) => set("password", e.target.value)}
            />
          )}
        </FormField>
        <FormField id="confirmPassword" label="Confirm password" error={errors.confirmPassword}>
          {(c) => (
            <Input
              {...c}
              type="password"
              autoComplete="new-password"
              value={values.confirmPassword}
              onChange={(e) => set("confirmPassword", e.target.value)}
            />
          )}
        </FormField>
        <Button type="submit" className="h-10 w-full" disabled={busy || status === "signed-in"}>
          {busy && <Loader2 className="animate-spin" data-icon="inline-start" />}
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthCard>
  );
}
