import { signOut } from "firebase/auth";
import { env } from "@/lib/env";
import { getFirebaseAuth } from "@/lib/firebase";

/** Mirrors the backend's standard error envelope (see docs/CONVENTIONS.md). */
export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string | null; details?: unknown };
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly requestId?: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const NETWORK_ERROR = new ApiError(0, "network_error", "Can't reach the VyaparAI server. Check your connection and try again.");

/** Session problems the user can only fix by signing in again. */
const SIGN_OUT_CODES = new Set(["token_revoked", "user_disabled"]);

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    return new ApiError(res.status, body.error.code, body.error.message, body.error.request_id ?? undefined, body.error.details);
  } catch {
    return new ApiError(res.status, "http_error", res.statusText || "Request failed");
  }
}

async function currentToken(forceRefresh = false): Promise<string> {
  const user = getFirebaseAuth().currentUser;
  if (!user) throw new ApiError(401, "missing_token", "Sign in to continue.");
  return user.getIdToken(forceRefresh);
}

interface RequestOptions extends Omit<RequestInit, "body" | "headers"> {
  body?: unknown;
  /** Set for multipart uploads; skips JSON encoding. */
  formData?: FormData;
  headers?: Record<string, string>;
}

/**
 * Authenticated request to the FastAPI backend. Attaches the Firebase ID token, retries once
 * with a refreshed token on 401, and signs the user out if the session was revoked.
 */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, formData, headers, ...rest } = options;

  const send = async (token: string) => {
    try {
      return await fetch(`${env.apiBaseUrl}${path}`, {
        ...rest,
        headers: {
          ...(formData ? {} : { "Content-Type": "application/json" }),
          Authorization: `Bearer ${token}`,
          ...headers,
        },
        body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
      });
    } catch {
      throw NETWORK_ERROR;
    }
  };

  let res = await send(await currentToken());
  if (res.status === 401) {
    const first = await parseError(res);
    if (SIGN_OUT_CODES.has(first.code)) {
      await signOut(getFirebaseAuth());
      throw first;
    }
    res = await send(await currentToken(true));
  }
  if (!res.ok) {
    const err = await parseError(res);
    if (res.status === 401) await signOut(getFirebaseAuth());
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Authenticated binary download (e.g. the original uploaded document). */
export async function apiFetchBlob(path: string): Promise<Blob> {
  const token = await currentToken();
  let res: Response;
  try {
    res = await fetch(`${env.apiBaseUrl}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  } catch {
    throw NETWORK_ERROR;
  }
  if (!res.ok) throw await parseError(res);
  return res.blob();
}

/** Multipart upload with progress (fetch can't report upload progress). */
export async function apiUpload<T>(path: string, formData: FormData, onProgress?: (percent: number) => void): Promise<T> {
  const token = await currentToken();
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${env.apiBaseUrl}${path}`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(NETWORK_ERROR);
    xhr.onload = () => {
      const res = new Response(xhr.responseText, { status: xhr.status, statusText: xhr.statusText });
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText) as T);
      else void parseError(res).then(reject);
    };
    xhr.send(formData);
  });
}

/** User-facing message for any error thrown by the API layer. */
export function errorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof ApiError) return error.message;
  return fallback;
}
