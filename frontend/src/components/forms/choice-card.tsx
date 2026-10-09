import type { ReactNode } from "react";
import { Field, FieldContent, FieldDescription, FieldLabel, FieldTitle } from "@/components/ui/field";

interface ChoiceCardProps {
  htmlFor: string;
  title: ReactNode;
  description?: string;
  /** The Checkbox or RadioGroupItem, with id === htmlFor. */
  control: ReactNode;
}

/** Large, tappable option for checkbox / radio choices (easier on mobile than bare inputs). */
export function ChoiceCard({ htmlFor, title, description, control }: ChoiceCardProps) {
  return (
    <FieldLabel htmlFor={htmlFor}>
      <Field orientation="horizontal">
        {control}
        <FieldContent>
          <FieldTitle>{title}</FieldTitle>
          {description && <FieldDescription>{description}</FieldDescription>}
        </FieldContent>
      </Field>
    </FieldLabel>
  );
}
