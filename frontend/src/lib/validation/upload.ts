import { UPLOAD_LIMITS } from "@/lib/constants";
import { formatFileSize } from "@/lib/format";

export interface FileCheck {
  file: File;
  error?: string;
}

export function checkFile(file: File): FileCheck {
  const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!(UPLOAD_LIMITS.acceptedExtensions as ReadonlyArray<string>).includes(ext))
    return { file, error: `${file.name}: this file type isn't supported. Use Excel, CSV, PDF or a photo (JPG/PNG).` };
  if (file.size === 0) return { file, error: `${file.name}: the file is empty.` };
  if (file.size > UPLOAD_LIMITS.maxFileSizeBytes)
    return {
      file,
      error: `${file.name} is ${formatFileSize(file.size)}. Files must be under ${formatFileSize(UPLOAD_LIMITS.maxFileSizeBytes)}.`,
    };
  return { file };
}
