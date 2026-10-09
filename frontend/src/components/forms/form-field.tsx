import type { ReactNode } from "react";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { cn } from "@/lib/utils";

/** Props to spread on the control so label, hint and error are announced together. */
export interface ControlProps {
  id: string;
  name: string;
  "aria-invalid": boolean | undefined;
  "aria-describedby": string | undefined;
}

interface FormFieldProps {
  id: string;
  label: string;
  optional?: boolean;
  description?: string;
  error?: string;
  className?: string;
  children: (control: ControlProps) => ReactNode;
}

export function FormField({ id, label, optional, description, error, className, children }: FormFieldProps) {
  const descId = description ? `${id}-description` : undefined;
  const errId = error ? `${id}-error` : undefined;
  const describedBy = [descId, errId].filter(Boolean).join(" ") || undefined;

  return (
    <Field data-invalid={error ? true : undefined} className={cn("gap-2", className)}>
      <FieldLabel htmlFor={id}>
        {label}
        {optional && <span className="font-normal text-muted-foreground">(optional)</span>}
      </FieldLabel>
      {children({ id, name: id, "aria-invalid": error ? true : undefined, "aria-describedby": describedBy })}
      {description && !error && <FieldDescription id={descId}>{description}</FieldDescription>}
      {error && (
        <p id={errId} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </Field>
  );
}

/** Focuses the first control with aria-invalid inside `root` — call after a failed submit. */
export function focusFirstInvalid(root: HTMLElement | null): void {
  requestAnimationFrame(() => {
    root?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  });
}
