"use client";

import { FileUp, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { RecentDocument } from "@/lib/types";

export function RecentUploadsWidget({ documents }: { documents: RecentDocument[] }) {
  if (!documents || documents.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Uploads</CardTitle>
        <CardDescription>Status of your recently uploaded documents</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {documents.map((doc) => (
            <div key={doc.id} className="flex items-center gap-4 text-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
                <FileUp className="h-4 w-4" />
              </div>
              <div className="flex-1 overflow-hidden">
                <p className="truncate font-medium leading-none">{doc.originalFilename}</p>
                <p className="text-muted-foreground mt-1 truncate">
                  {new Date(doc.uploadedAt).toLocaleDateString()}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {doc.status === "done" && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                {doc.status === "processing" && <Clock className="h-4 w-4 text-amber-500" />}
                {doc.status === "failed" && <XCircle className="h-4 w-4 text-red-500" />}
                <span className="capitalize text-muted-foreground">{doc.status}</span>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
