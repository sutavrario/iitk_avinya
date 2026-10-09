"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { MAPPABLE_FIELDS, REQUIRED_FIELDS, fieldLabel } from "@/lib/ingestion";
import type { ExtractableField, ExtractionInfo, IngestionRecordType, ProcessRequest } from "@/lib/types";
import { cn } from "@/lib/utils";

const NONE = "__none__";
type Mapping = Partial<Record<ExtractableField, string[]>>;

interface Props {
  extraction: ExtractionInfo;
  recordType: IngestionRecordType;
  submitting: boolean;
  onSubmit: (request: ProcessRequest) => void;
  onCancel?: () => void;
}

export function ColumnMappingPanel({ extraction, recordType, submitting, onSubmit, onCancel }: Props) {
  const [mapping, setMapping] = useState<Mapping>(() => ({ ...extraction.mapping }));
  const [type, setType] = useState<IngestionRecordType>(recordType);
  const [error, setError] = useState<string | null>(null);
  const columns = extraction.columns;
  const columnItems = [{ value: NONE, label: "— Not in this file —" }, ...columns.map((c) => ({ value: c, label: c }))];

  const used = new Map<string, ExtractableField>();
  for (const [f, cols] of Object.entries(mapping)) for (const c of cols ?? []) used.set(c, f as ExtractableField);

  function setSingle(field: ExtractableField, column: string) {
    setError(null);
    setMapping((m) => ({ ...m, [field]: column === NONE ? [] : [column] }));
  }

  function toggleMulti(field: ExtractableField, column: string, checked: boolean) {
    setMapping((m) => {
      const current = m[field] ?? [];
      return { ...m, [field]: checked ? [...current, column] : current.filter((c) => c !== column) };
    });
  }

  function submit() {
    const missing = REQUIRED_FIELDS.filter((f) => !(mapping[f]?.length));
    if (missing.length) {
      setError(`Choose a column for: ${missing.map((f) => fieldLabel(f, type)).join(", ")}.`);
      return;
    }
    const clash = Object.entries(mapping).flatMap(([f, cols]) => (cols ?? []).map((c) => [c, f] as const));
    const counts = new Map<string, number>();
    for (const [c] of clash) counts.set(c, (counts.get(c) ?? 0) + 1);
    const repeated = [...counts.entries()].filter(([, n]) => n > 1).map(([c]) => c);
    if (repeated.length) {
      setError(`Each column can be used once. "${repeated[0]}" is chosen more than once.`);
      return;
    }
    onSubmit({ columnMapping: mapping, sheetName: extraction.sheetName, recordType: type });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Match your columns</CardTitle>
        <CardDescription>
          Tell us which column holds each detail. We&apos;ve pre-filled our best guesses
          {extraction.headerRowNumber ? ` (headings found on row ${extraction.headerRowNumber})` : ""}.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Label htmlFor="record-type">These rows are</Label>
          <Select
            items={[
              { value: "sales_invoice", label: "Sales invoices (customers owe me)" },
              { value: "purchase_invoice", label: "Purchase bills (I owe suppliers)" },
            ]}
            value={type}
            onValueChange={(v) => v && setType(v as IngestionRecordType)}
          >
            <SelectTrigger id="record-type" className="w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="sales_invoice">Sales invoices (customers owe me)</SelectItem>
              <SelectItem value="purchase_invoice">Purchase bills (I owe suppliers)</SelectItem>
            </SelectContent>
          </Select>
          {extraction.sheetNames.length > 1 && extraction.sheetName && (
            <span className="text-sm text-muted-foreground">
              Sheet: <span className="font-medium text-foreground">{extraction.sheetName}</span>
            </span>
          )}
        </div>

        <div className="grid gap-x-6 gap-y-4 md:grid-cols-2">
          {MAPPABLE_FIELDS.map(({ field, hint, multi }) => {
            const required = REQUIRED_FIELDS.includes(field);
            const confidence = extraction.mappingConfidence[field];
            const id = `map-${field}`;
            return (
              <div key={field} className={cn("space-y-1.5", multi && "md:col-span-2")}>
                <div className="flex items-center gap-2">
                  <Label htmlFor={multi ? undefined : id} id={`${id}-label`}>
                    {fieldLabel(field, type)}
                    {required ? <span className="text-destructive" aria-hidden> *</span> : null}
                    {required && <span className="sr-only"> (required)</span>}
                  </Label>
                  {confidence !== undefined && confidence < 0.8 && (mapping[field]?.length ?? 0) > 0 && (
                    <Badge variant="outline" className="border-warning/50 text-warning">
                      Check this
                    </Badge>
                  )}
                </div>
                {multi ? (
                  <div role="group" aria-labelledby={`${id}-label`} className="flex flex-wrap gap-x-4 gap-y-2 rounded-lg border p-3">
                    {columns.map((c) => {
                      const takenBy = used.get(c);
                      const checked = mapping[field]?.includes(c) ?? false;
                      return (
                        <div key={c} className="flex items-center gap-2">
                          <Checkbox
                            id={`${id}-${c}`}
                            checked={checked}
                            disabled={!checked && takenBy !== undefined && takenBy !== field}
                            onCheckedChange={(v) => toggleMulti(field, c, v)}
                          />
                          <Label htmlFor={`${id}-${c}`} className="font-normal">
                            {c}
                          </Label>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <Select items={columnItems} value={mapping[field]?.[0] ?? NONE} onValueChange={(v) => v && setSingle(field, v)}>
                    <SelectTrigger id={id} className="w-full" aria-describedby={`${id}-hint`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {columnItems.map((c) => (
                        <SelectItem key={c.value} value={c.value}>
                          {c.label}
                          {c.value !== NONE && used.get(c.value) && used.get(c.value) !== field ? " (in use)" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                <p id={`${id}-hint`} className="text-xs text-muted-foreground">
                  {hint}
                </p>
              </div>
            );
          })}
        </div>

        {extraction.sampleRows.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">First rows of your file</p>
            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    {columns.map((c) => (
                      <TableHead key={c} className="whitespace-nowrap">
                        {c}
                        {used.get(c) && (
                          <span className="ml-1.5 text-xs font-normal text-primary">→ {fieldLabel(used.get(c)!, type)}</span>
                        )}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {extraction.sampleRows.map((row, i) => (
                    <TableRow key={i}>
                      {columns.map((c) => (
                        <TableCell key={c} className="whitespace-nowrap text-muted-foreground">
                          {row[c] || "—"}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </CardContent>
      <CardFooter className="justify-end gap-2 border-t">
        {onCancel && (
          <Button variant="ghost" onClick={onCancel} disabled={submitting}>
            Cancel
          </Button>
        )}
        <Button onClick={submit} disabled={submitting}>
          {submitting && <Loader2 className="animate-spin" data-icon="inline-start" />}
          Read file with these columns
        </Button>
      </CardFooter>
    </Card>
  );
}
