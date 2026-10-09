"use client";

import { Loader2, Plus } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { FormField, focusFirstInvalid } from "@/components/forms/form-field";
import { SelectField } from "@/components/forms/select-field";
import { PAYMENT_METHOD_OPTIONS } from "@/components/records/record-columns";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { FieldLegend, FieldSet } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import { todayIso } from "@/lib/format";
import type { Payment, PaymentDirection, PaymentMethod } from "@/lib/types";
import { hasErrors, type FieldErrors } from "@/lib/validation/common";
import { parseAmount, validatePayment, type PaymentFormValues } from "@/lib/validation/records";

const empty = (): PaymentFormValues => ({
  partyName: "",
  date: todayIso(),
  direction: "received",
  amount: "",
  method: "upi",
  reference: "",
  invoiceNumber: "",
});

export function AddPaymentDialog({ businessId, onCreated }: { businessId: string; onCreated: (payment: Payment) => void }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<PaymentFormValues>(empty);
  const [errors, setErrors] = useState<FieldErrors<keyof PaymentFormValues>>({});
  const [saving, setSaving] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  function set<K extends keyof PaymentFormValues>(k: K, v: PaymentFormValues[K]) {
    setValues((p) => ({ ...p, [k]: v }));
    if (errors[k]) setErrors((p) => ({ ...p, [k]: undefined }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validatePayment(values);
    if (hasErrors(errs)) {
      setErrors(errs);
      focusFirstInvalid(formRef.current);
      return;
    }
    setSaving(true);
    try {
      const payment = await api.records.createPayment(businessId, {
        partyName: values.partyName.trim(),
        date: values.date,
        direction: values.direction,
        amount: parseAmount(values.amount),
        method: values.method,
        ...(values.reference.trim() && { reference: values.reference.trim() }),
        ...(values.invoiceNumber.trim() && { invoiceNumber: values.invoiceNumber.trim() }),
      });
      onCreated(payment);
      toast.success("Payment recorded");
      setOpen(false);
      setValues(empty());
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't save the payment. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  const received = values.direction === "received";

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setErrors({});
      }}
    >
      <DialogTrigger render={<Button variant="outline" />}>
        <Plus data-icon="inline-start" /> Record payment
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Record a payment</DialogTitle>
          <DialogDescription>Money you received from a customer or paid to a supplier.</DialogDescription>
        </DialogHeader>
        <form ref={formRef} onSubmit={submit} noValidate className="grid gap-4">
          <FieldSet>
            <FieldLegend variant="label">Type</FieldLegend>
            <RadioGroup
              value={values.direction}
              onValueChange={(v) => set("direction", v as PaymentDirection)}
              className="flex gap-6"
            >
              {(["received", "paid"] as const).map((d) => (
                <div key={d} className="flex items-center gap-2">
                  <RadioGroupItem id={`dir-${d}`} value={d} />
                  <Label htmlFor={`dir-${d}`}>{d === "received" ? "Money received" : "Money paid"}</Label>
                </div>
              ))}
            </RadioGroup>
          </FieldSet>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="pay-party" label={received ? "Received from" : "Paid to"} error={errors.partyName}>
              {(c) => <Input {...c} value={values.partyName} onChange={(e) => set("partyName", e.target.value)} />}
            </FormField>
            <FormField id="pay-amount" label="Amount (₹)" error={errors.amount}>
              {(c) => <Input {...c} inputMode="decimal" placeholder="10,000" value={values.amount} onChange={(e) => set("amount", e.target.value)} />}
            </FormField>
            <FormField id="pay-date" label="Date" error={errors.date}>
              {(c) => <Input {...c} type="date" max={todayIso()} value={values.date} onChange={(e) => set("date", e.target.value)} />}
            </FormField>
            <SelectField
              id="pay-method"
              label="Method"
              value={values.method}
              onChange={(v) => set("method", v as PaymentMethod)}
              options={PAYMENT_METHOD_OPTIONS}
            />
            <FormField id="pay-ref" label="UTR / cheque no." optional>
              {(c) => <Input {...c} value={values.reference} onChange={(e) => set("reference", e.target.value)} />}
            </FormField>
            {received && (
              <FormField id="pay-invoice" label="Against invoice" optional>
                {(c) => <Input {...c} placeholder="INV-1001" value={values.invoiceNumber} onChange={(e) => set("invoiceNumber", e.target.value)} />}
              </FormField>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="animate-spin" data-icon="inline-start" />}
              {saving ? "Saving…" : "Save payment"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
