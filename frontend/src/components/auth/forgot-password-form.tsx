"use client";

import { CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AuthCard } from "@/components/auth/auth-card";
import { FormField } from "@/components/forms/form-field";
import { useAuth } from "@/components/providers/auth-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { validateEmail } from "@/lib/validation/auth";

export function ForgotPasswordForm() {
  const { sendPasswordReset } = useAuth();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const err = validateEmail(email);
    if (err) return setError(err);
    setBusy(true);
    try {
      await sendPasswordReset(email.trim());
    } catch {
      // Same outcome whether or not the account exists, to avoid revealing registered emails.
    }
    setSent(true);
    setBusy(false);
  }

  return (
    <AuthCard
      title="Reset your password"
      description="We'll email you a link to choose a new password."
      footer={
        <Link href="/sign-in" className="font-medium text-primary underline-offset-4 hover:underline">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <Alert role="status">
          <CheckCircle2 className="text-success" aria-hidden />
          <AlertDescription>
            If an account exists for {email.trim()}, a reset link is on its way. Check your inbox and spam folder.
          </AlertDescription>
        </Alert>
      ) : (
        <form onSubmit={submit} noValidate className="space-y-4">
          <FormField id="email" label="Email" error={error}>
            {(c) => (
              <Input
                {...c}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  setError(undefined);
                }}
              />
            )}
          </FormField>
          <Button type="submit" className="h-10 w-full" disabled={busy}>
            {busy && <Loader2 className="animate-spin" data-icon="inline-start" />}
            Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
