import type { Metadata } from "next";
import { Suspense } from "react";
import { FullPageLoader } from "@/components/auth/full-page-status";
import { SignUpForm } from "@/components/auth/sign-up-form";

export const metadata: Metadata = { title: "Create account" };

export default function SignUpPage() {
  return (
    <Suspense fallback={<FullPageLoader />}>
      <SignUpForm />
    </Suspense>
  );
}
