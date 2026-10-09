"use client";

import { Info } from "lucide-react";
import { SelectField } from "@/components/forms/select-field";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Switch } from "@/components/ui/switch";
import { LANGUAGES } from "@/lib/constants";
import type { LanguageCode, UserPreferences } from "@/lib/types";

const LANGUAGE_OPTIONS = LANGUAGES.map((l) => ({
  value: l.value,
  label: l.value === "en" ? l.label : `${l.nativeLabel} (${l.label})`,
}));

interface Props {
  value: UserPreferences;
  onChange: (next: UserPreferences) => void;
}

export function LanguageSettings({ value, onChange }: Props) {
  const set = <K extends keyof UserPreferences>(k: K, v: UserPreferences[K]) => onChange({ ...value, [k]: v });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Language</CardTitle>
        <CardDescription>Choose how VyaparAI talks to you.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-5 sm:grid-cols-2">
          <SelectField
            id="copilotLanguage"
            label="Copilot reply language"
            description="Answers from the AI copilot will be in this language."
            value={value.copilotLanguage}
            onChange={(v) => set("copilotLanguage", v as LanguageCode)}
            options={LANGUAGE_OPTIONS}
          />
          <SelectField
            id="interfaceLanguage"
            label="App language"
            description="Menus and buttons. Currently English only; more coming soon."
            value={value.interfaceLanguage}
            onChange={(v) => set("interfaceLanguage", v as LanguageCode)}
            options={LANGUAGE_OPTIONS}
          />
        </div>

        <div className="space-y-4">
          <Field orientation="horizontal">
            <FieldContent>
              <FieldLabel htmlFor="alwaysTranslate">Always reply in my language</FieldLabel>
              <FieldDescription>
                Even if you type your question in English, answers come back in your chosen language.
              </FieldDescription>
            </FieldContent>
            <Switch
              id="alwaysTranslate"
              checked={value.alwaysTranslateReplies}
              onCheckedChange={(c) => set("alwaysTranslateReplies", c)}
            />
          </Field>
          <Field orientation="horizontal">
            <FieldContent>
              <FieldLabel htmlFor="showOriginal">Show English alongside translations</FieldLabel>
              <FieldDescription>Helpful for sharing answers with your accountant.</FieldDescription>
            </FieldContent>
            <Switch
              id="showOriginal"
              checked={value.showOriginalAlongsideTranslation}
              onCheckedChange={(c) => set("showOriginalAlongsideTranslation", c)}
            />
          </Field>
        </div>

        {value.interfaceLanguage !== "en" && (
          <p className="flex gap-2 rounded-lg bg-muted p-3 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            Your choice is saved. Menus will switch to this language once translations are available.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
