"use client";

import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { BusinessProfileCard } from "@/components/settings/business-profile-card";
import { LanguageSettings } from "@/components/settings/language-settings";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAsyncData } from "@/hooks/use-async-data";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/api-client";
import { useTranslation } from "@/lib/i18n";
import type { UserPreferences } from "@/lib/types";

const loadPreferences = () => api.preferences.get();

export function SettingsView() {
  const saved = useAsyncData(loadPreferences);
  const [draft, setDraft] = useState<UserPreferences | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (saved.data) setDraft(saved.data);
  }, [saved.data]);

  const dirty = Boolean(draft && saved.data && JSON.stringify(draft) !== JSON.stringify(saved.data));

  async function save() {
    if (!draft) return;
    setSaving(true);
    try {
      saved.setData(await api.preferences.save(draft));
      toast.success("Preferences saved");
    } catch (err) {
      toast.error(errorMessage(err, "Couldn't save preferences. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  const { t } = useTranslation();

  return (
    <>
      <PageHeader title={t("nav.settings", "Settings")} description="Language and business preferences." />
      <BusinessProfileCard />

      {saved.status === "error" && <ErrorState message="Couldn't load your preferences." onRetry={saved.reload} />}
      {!draft && saved.status === "loading" && <Skeleton className="h-64 w-full rounded-xl" />}
      {draft && (
        <>
          <LanguageSettings value={draft} onChange={setDraft} />
          <div className="sticky bottom-4 flex items-center justify-end gap-3 rounded-xl border bg-background/95 p-3 shadow-sm backdrop-blur">
            <p className="mr-auto text-sm text-muted-foreground" aria-live="polite">
              {dirty ? "You have unsaved changes." : "All changes saved."}
            </p>
            <Button variant="ghost" disabled={!dirty || saving} onClick={() => saved.data && setDraft(saved.data)}>
              Discard
            </Button>
            <Button disabled={!dirty || saving} onClick={() => void save()}>
              {saving && <Loader2 className="animate-spin" data-icon="inline-start" />}
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </>
      )}
    </>
  );
}
