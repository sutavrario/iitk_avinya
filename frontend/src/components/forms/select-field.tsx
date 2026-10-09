"use client";

import { FormField } from "@/components/forms/form-field";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Option } from "@/lib/constants";

interface SelectFieldProps<T extends string> {
  id: string;
  label: string;
  value: T | "";
  onChange: (value: T) => void;
  options: ReadonlyArray<Option<T>>;
  placeholder?: string;
  optional?: boolean;
  description?: string;
  error?: string;
  className?: string;
}

export function SelectField<T extends string>({
  id,
  label,
  value,
  onChange,
  options,
  placeholder = "Select…",
  optional,
  description,
  error,
  className,
}: SelectFieldProps<T>) {
  return (
    <FormField
      id={id}
      label={label}
      optional={optional}
      description={description}
      error={error}
      className={className}
    >
      {(control) => (
        <Select
          items={options.map((o) => ({ value: o.value, label: o.label }))}
          value={value === "" ? null : value}
          onValueChange={(v) => {
            if (v !== null) onChange(v as T);
          }}
        >
          <SelectTrigger
            id={control.id}
            aria-invalid={control["aria-invalid"]}
            aria-describedby={control["aria-describedby"]}
            className="w-full"
          >
            <SelectValue placeholder={placeholder} />
          </SelectTrigger>
          <SelectContent>
            {options.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </FormField>
  );
}
