"use client";

import { UploadCloud } from "lucide-react";
import { useId, useRef, useState } from "react";
import { UPLOAD_LIMITS } from "@/lib/constants";
import { formatFileSize } from "@/lib/format";
import { cn } from "@/lib/utils";

interface UploadDropzoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

export function UploadDropzone({ onFiles, disabled }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const [dragging, setDragging] = useState(false);

  function handle(list: FileList | null) {
    if (list && list.length) onFiles(Array.from(list));
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) handle(e.dataTransfer.files);
      }}
      className={cn(
        "relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed bg-card px-6 py-12 text-center transition-colors",
        dragging ? "border-primary bg-primary/5" : "border-border",
        disabled && "opacity-60",
      )}
    >
      <div className="mb-4 grid size-12 place-items-center rounded-full bg-primary/10 text-primary">
        <UploadCloud className="size-6" aria-hidden />
      </div>
      <p className="font-medium">
        Drag files here, or{" "}
        <button
          type="button"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          className="text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 rounded-sm"
          aria-describedby={hintId}
        >
          browse your device
        </button>
      </p>
      <p id={hintId} className="mt-1 text-sm text-muted-foreground">
        Excel, CSV, PDF or photos · up to {formatFileSize(UPLOAD_LIMITS.maxFileSizeBytes)} each ·{" "}
        {UPLOAD_LIMITS.maxFilesPerBatch} files at a time
      </p>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        accept={UPLOAD_LIMITS.acceptedExtensions.join(",")}
        onChange={(e) => {
          handle(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
