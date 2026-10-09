import type { Metadata } from "next";
import { Suspense } from "react";
import { FullPageLoader } from "@/components/auth/full-page-status";
import { SignInForm } from "@/components/auth/sign-in-form";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    <Suspense fallback={<FullPageLoader />}>
      <SignInForm />
    </Suspense>
  );
}
