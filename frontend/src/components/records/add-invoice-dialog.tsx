"use client";

import { Loader2, Plus } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { FormField, focusFirstInvalid } from "@/components/forms/form-field";
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
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import { todayIso } from "@/lib/format";
import type { Invoice } from "@/lib/types";
import { hasErrors, type FieldErrors } from "@/lib/validation/common";
import { parseAmount, validateInvoice, type InvoiceFormValues } from "@/lib/validation/records";

const empty = (): InvoiceFormValues => ({
  invoiceNumber: "",
  customerName: "",
  issueDate: todayIso(),
  dueDate: "",
  amount: "",
  gstAmount: "",
});

export function AddInvoiceDialog({ businessId, onCreated }: { businessId: string; onCreated: (invoice: Invoice) => void }) {
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<InvoiceFormValues>(empty);
  const [errors, setErrors] = useState<FieldErrors<keyof InvoiceFormValues>>({});
  const [saving, setSaving] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const set = (k: keyof InvoiceFormValues, v: string) => {
    setValues((p) => ({ ...p, [k]: v }));
    if (errors[k]) setErrors((p) => ({ ...p, [k]: undefined }));
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateInvoice(values);
    if (hasErrors(errs)) {
      setErrors(errs);
      focusFirstInvalid(formRef.current);
      return;
    }
    setSaving(true);
    try {
      const invoice = await api.records.createInvoice(businessId, {
        invoiceNumber: values.invoiceNumber.trim(),
        customerName: values.customerName.trim(),
        issueDate: values.issueDate,
        dueDate: values.dueDate,
        amount: parseAmount(values.amount),
        ...(values.gstAmount.trim() && { gstAmount: parseAmount(values.gstAmount) }),
      });
      onCreated(invoice);
      toast.success(`Invoice ${invoice.invoiceNumber} added`);
      setOpen(false);
      setValues(empty());
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't save the invoice. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setErrors({});
      }}
    >
      <DialogTrigger render={<Button />}>
        <Plus data-icon="inline-start" /> Add invoice
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add an invoice</DialogTitle>
          <DialogDescription>For a bill you raised to a customer. Amounts in ₹, including GST.</DialogDescription>
        </DialogHeader>
        <form ref={formRef} onSubmit={submit} noValidate className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="inv-number" label="Invoice number" error={errors.invoiceNumber}>
              {(c) => <Input {...c} placeholder="INV-1006" value={values.invoiceNumber} onChange={(e) => set("invoiceNumber", e.target.value)} />}
            </FormField>
            <FormField id="inv-customer" label="Customer name" error={errors.customerName}>
              {(c) => <Input {...c} value={values.customerName} onChange={(e) => set("customerName", e.target.value)} />}
            </FormField>
            <FormField id="inv-issue" label="Invoice date" error={errors.issueDate}>
              {(c) => <Input {...c} type="date" value={values.issueDate} onChange={(e) => set("issueDate", e.target.value)} />}
            </FormField>
            <FormField id="inv-due" label="Due date" error={errors.dueDate}>
              {(c) => <Input {...c} type="date" min={values.issueDate} value={values.dueDate} onChange={(e) => set("dueDate", e.target.value)} />}
            </FormField>
            <FormField id="inv-amount" label="Total amount (₹)" error={errors.amount}>
              {(c) => <Input {...c} inputMode="decimal" placeholder="25,000" value={values.amount} onChange={(e) => set("amount", e.target.value)} />}
            </FormField>
            <FormField id="inv-gst" label="GST included (₹)" optional error={errors.gstAmount}>
              {(c) => <Input {...c} inputMode="decimal" placeholder="3,814" value={values.gstAmount} onChange={(e) => set("gstAmount", e.target.value)} />}
            </FormField>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="animate-spin" data-icon="inline-start" />}
              {saving ? "Saving…" : "Save invoice"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
