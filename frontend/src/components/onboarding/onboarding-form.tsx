"use client";

import { ArrowLeft, ArrowRight, FileUp, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { ChoiceCard } from "@/components/forms/choice-card";
import { FormField, focusFirstInvalid } from "@/components/forms/form-field";
import { SelectField } from "@/components/forms/select-field";
import { StepIndicator } from "@/components/onboarding/step-indicator";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useWorkspace } from "@/components/providers/workspace-provider";
import { api } from "@/lib/api";
import { ApiError, errorMessage } from "@/lib/api-client";
import {
  BUSINESS_GOALS,
  BUSINESS_TYPES,
  FINANCIAL_YEAR_OPTIONS,
  INDIAN_STATES,
  INDUSTRIES,
  LANGUAGES,
  PAYMENT_TERMS_OPTIONS,
} from "@/lib/constants";
import type { Business, BusinessGoal, BusinessProfile, FinancialYearStart, LanguageCode } from "@/lib/types";
import { hasErrors, type FieldErrors } from "@/lib/validation/common";
import {
  initialOnboardingValues,
  ONBOARDING_STEPS,
  type OnboardingField,
  type OnboardingFormValues,
  validateOnboarding,
  validateStep,
} from "@/lib/validation/onboarding";

const STATE_OPTIONS = INDIAN_STATES.map((s) => ({ value: s, label: s }));

function toProfile(v: OnboardingFormValues): BusinessProfile {
  return {
    businessName: v.businessName.trim(),
    industry: v.industry,
    businessType: v.businessType,
    location: { city: v.city.trim(), state: v.state, ...(v.pincode.trim() && { pincode: v.pincode.trim() }) },
    currency: "INR",
    financialYearStart: v.financialYearStart,
    paymentTermsDays: v.paymentTerms ? Number(v.paymentTerms) : null,
    goals: v.goals,
    preferredLanguage: v.preferredLanguage,
    ...(v.gstin.trim() && { gstin: v.gstin.trim().toUpperCase() }),
  };
}

function fromProfile(p: BusinessProfile): OnboardingFormValues {
  return {
    businessName: p.businessName,
    industry: p.industry,
    businessType: p.businessType,
    city: p.location.city,
    state: p.location.state,
    pincode: p.location.pincode ?? "",
    gstin: p.gstin ?? "",
    financialYearStart: p.financialYearStart,
    paymentTerms: p.paymentTermsDays === null ? "" : String(p.paymentTermsDays),
    goals: p.goals,
    preferredLanguage: p.preferredLanguage,
  };
}

/** Maps a FastAPI validation error location (e.g. ["body","location","pincode"]) to a form field. */
function serverFieldErrors(err: unknown): FieldErrors<OnboardingField> {
  if (!(err instanceof ApiError) || err.code !== "validation_error" || !Array.isArray(err.details)) return {};
  const out: FieldErrors<OnboardingField> = {};
  for (const d of err.details as Array<{ loc?: unknown[]; msg?: string }>) {
    const field = d.loc?.[d.loc.length - 1];
    if (typeof field === "string" && field in initialOnboardingValues) {
      out[field as OnboardingField] = "Please check this value.";
    }
  }
  return out;
}

export function OnboardingForm({ existing }: { existing: Business | null }) {
  const router = useRouter();
  const { refresh } = useWorkspace();
  const formRef = useRef<HTMLFormElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [step, setStep] = useState(0);
  const [values, setValues] = useState<OnboardingFormValues>(() =>
    existing ? fromProfile(existing) : initialOnboardingValues,
  );
  const [errors, setErrors] = useState<FieldErrors<OnboardingField>>({});
  const [submitting, setSubmitting] = useState(false);
  const isEditing = existing !== null;

  const isLast = step === ONBOARDING_STEPS.length - 1;

  function set<K extends OnboardingField>(key: K, value: OnboardingFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
    // Clear a field's error as soon as the user edits it.
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  }

  function toggleGoal(goal: BusinessGoal, checked: boolean) {
    set("goals", checked ? [...values.goals, goal] : values.goals.filter((g) => g !== goal));
  }

  function goTo(next: number) {
    setStep(next);
    requestAnimationFrame(() => headingRef.current?.focus());
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const stepErrors = validateStep(step, values);
    if (hasErrors(stepErrors)) {
      setErrors(stepErrors);
      focusFirstInvalid(formRef.current);
      return;
    }
    if (!isLast) return goTo(step + 1);

    const allErrors = validateOnboarding(values);
    if (hasErrors(allErrors)) {
      setErrors(allErrors);
      const firstBadStep = ONBOARDING_STEPS.findIndex((s) =>
        s.fields.some((f: OnboardingField) => allErrors[f]),
      );
      goTo(Math.max(0, firstBadStep));
      return;
    }

    setSubmitting(true);
    try {
      const profile = toProfile(values);
      if (existing) await api.businesses.update(existing.id, profile);
      else await api.businesses.create(profile);
      await refresh();
      toast.success(isEditing ? "Business details updated" : "Your business is set up!");
      router.push(isEditing ? "/settings" : "/dashboard");
    } catch (err) {
      const fieldErrors = serverFieldErrors(err);
      if (hasErrors(fieldErrors)) {
        setErrors(fieldErrors);
        const badStep = ONBOARDING_STEPS.findIndex((s) => s.fields.some((f: OnboardingField) => fieldErrors[f]));
        goTo(Math.max(0, badStep));
      }
      toast.error(errorMessage(err, "Couldn't save your details. Please try again."));
      setSubmitting(false);
    }
  }

  const current = ONBOARDING_STEPS[step];

  return (
    <form ref={formRef} onSubmit={handleSubmit} noValidate className="space-y-6">
      <StepIndicator steps={ONBOARDING_STEPS} current={step} />

      <Card>
        <CardHeader>
          <CardTitle>
            <h2 ref={headingRef} tabIndex={-1} className="text-lg outline-none">
              Step {step + 1} of {ONBOARDING_STEPS.length}: {current?.title}
            </h2>
          </CardTitle>
          <CardDescription>
            {step === 0 && "The basics, so your dashboard and reports look right."}
            {step === 1 && "Helps us calculate due dates, overdue amounts and yearly summaries."}
            {step === 2 && "We'll focus your dashboard and copilot on what matters to you."}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          {step === 0 && (
            <>
              <FormField id="businessName" label="Business name" error={errors.businessName}>
                {(c) => (
                  <Input
                    {...c}
                    autoComplete="organization"
                    placeholder="e.g. Sharma General Store"
                    value={values.businessName}
                    onChange={(e) => set("businessName", e.target.value)}
                  />
                )}
              </FormField>
              <div className="grid gap-5 sm:grid-cols-2">
                <SelectField
                  id="industry"
                  label="Industry"
                  value={values.industry}
                  onChange={(v) => set("industry", v)}
                  options={INDUSTRIES}
                  placeholder="Choose industry"
                  error={errors.industry}
                />
                <SelectField
                  id="businessType"
                  label="Business type"
                  optional
                  value={values.businessType}
                  onChange={(v) => set("businessType", v)}
                  options={BUSINESS_TYPES}
                  placeholder="Choose type"
                />
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <FormField id="city" label="City / town" error={errors.city}>
                  {(c) => (
                    <Input
                      {...c}
                      autoComplete="address-level2"
                      placeholder="e.g. Pune"
                      value={values.city}
                      onChange={(e) => set("city", e.target.value)}
                    />
                  )}
                </FormField>
                <SelectField
                  id="state"
                  label="State / UT"
                  value={values.state}
                  onChange={(v) => set("state", v)}
                  options={STATE_OPTIONS}
                  placeholder="Choose state"
                  error={errors.state}
                />
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <FormField id="pincode" label="PIN code" optional error={errors.pincode}>
                  {(c) => (
                    <Input
                      {...c}
                      inputMode="numeric"
                      autoComplete="postal-code"
                      maxLength={6}
                      placeholder="411001"
                      value={values.pincode}
                      onChange={(e) => set("pincode", e.target.value.replace(/\D/g, ""))}
                    />
                  )}
                </FormField>
                <FormField
                  id="gstin"
                  label="GSTIN"
                  optional
                  description="Add it now or later — only needed for GST summaries."
                  error={errors.gstin}
                >
                  {(c) => (
                    <Input
                      {...c}
                      maxLength={15}
                      className="uppercase placeholder:normal-case"
                      placeholder="15-character GST number"
                      value={values.gstin}
                      onChange={(e) => set("gstin", e.target.value.toUpperCase())}
                    />
                  )}
                </FormField>
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <FormField id="currency" label="Default currency" description="All amounts are shown in Indian Rupees.">
                {(c) => <Input {...c} value="₹ INR — Indian Rupee" readOnly disabled />}
              </FormField>
              <FieldSet>
                <FieldLegend variant="label">Financial year</FieldLegend>
                <RadioGroup
                  value={values.financialYearStart}
                  onValueChange={(v) => set("financialYearStart", v as FinancialYearStart)}
                  className="grid gap-3 sm:grid-cols-2"
                >
                  {FINANCIAL_YEAR_OPTIONS.map((o) => (
                    <ChoiceCard
                      key={o.value}
                      htmlFor={`fy-${o.value}`}
                      title={o.label}
                      description={o.description}
                      control={<RadioGroupItem id={`fy-${o.value}`} value={o.value} />}
                    />
                  ))}
                </RadioGroup>
              </FieldSet>
              <SelectField
                id="paymentTerms"
                label="How soon do customers usually pay you?"
                optional
                description="Used to flag invoices as overdue. Not sure? Skip it — you can set it later."
                value={values.paymentTerms}
                onChange={(v) => set("paymentTerms", v)}
                options={PAYMENT_TERMS_OPTIONS}
                placeholder="Choose typical payment terms"
              />
            </>
          )}

          {step === 2 && (
            <>
              <FieldSet>
                <FieldLegend variant="label">
                  What do you want help with?{" "}
                  <span className="font-normal text-muted-foreground">(optional, choose any)</span>
                </FieldLegend>
                <div className="grid gap-3 sm:grid-cols-2">
                  {BUSINESS_GOALS.map((g) => (
                    <ChoiceCard
                      key={g.value}
                      htmlFor={`goal-${g.value}`}
                      title={g.label}
                      description={g.description}
                      control={
                        <Checkbox
                          id={`goal-${g.value}`}
                          checked={values.goals.includes(g.value)}
                          onCheckedChange={(checked) => toggleGoal(g.value, checked)}
                        />
                      }
                    />
                  ))}
                </div>
              </FieldSet>
              <SelectField
                id="preferredLanguage"
                label="Preferred language"
                description="The copilot will reply in this language. You can change it anytime."
                value={values.preferredLanguage}
                onChange={(v) => set("preferredLanguage", v as LanguageCode)}
                options={LANGUAGES.map((l) => ({
                  value: l.value,
                  label: l.value === "en" ? l.label : `${l.nativeLabel} (${l.label})`,
                }))}
              />
              <div className="flex gap-3 rounded-lg border border-dashed bg-muted/40 p-4 text-sm">
                <FileUp className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <p className="text-muted-foreground">
                  <span className="font-medium text-foreground">No files needed right now.</span> After setup,
                  you can upload sales sheets, invoices and bank statements from the Documents page whenever
                  you&apos;re ready.
                </p>
              </div>
            </>
          )}
        </CardContent>

        <CardFooter className="justify-between gap-2 border-t">
          <Button
            type="button"
            variant="ghost"
            onClick={() => goTo(step - 1)}
            disabled={step === 0 || submitting}
          >
            <ArrowLeft data-icon="inline-start" /> Back
          </Button>
          <Button type="submit" disabled={submitting} className="min-w-32">
            {submitting ? (
              <>
                <Loader2 className="animate-spin" data-icon="inline-start" /> Saving…
              </>
            ) : isLast ? (
              isEditing ? "Save changes" : "Finish setup"
            ) : (
              <>
                Continue <ArrowRight data-icon="inline-end" />
              </>
            )}
          </Button>
        </CardFooter>
      </Card>
      <p className="text-center text-xs text-muted-foreground">
        Fields marked (optional) can be skipped and filled in later from Settings.
      </p>
    </form>
  );
}
