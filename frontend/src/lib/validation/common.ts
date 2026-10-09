/** Map of field name -> human-readable error message. Empty object means valid. */
export type FieldErrors<T extends string = string> = Partial<Record<T, string>>;

export function hasErrors(errors: FieldErrors): boolean {
  return Object.values(errors).some(Boolean);
}

export const PINCODE_PATTERN = /^[1-9][0-9]{5}$/;
/** 15-character GSTIN: 2-digit state code, PAN, entity number, 'Z', checksum. */
export const GSTIN_PATTERN = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
