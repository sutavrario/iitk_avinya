/**
 * Centralised, typed access to public environment variables.
 * Only NEXT_PUBLIC_* values are exposed to the browser. The Firebase *web* config is
 * public by design (access is enforced by Auth, security rules and the backend);
 * Firebase Admin credentials must never appear here.
 */
function optional(value: string | undefined, fallback = ""): string {
  return value ?? fallback;
}

const useEmulators = process.env.NEXT_PUBLIC_FIREBASE_USE_EMULATORS === "true";

/** Must match EMULATOR_PROJECT_ID in the backend so emulator tokens verify. */
export const EMULATOR_PROJECT_ID = "demo-vyaparai";

export const env = {
  apiBaseUrl: optional(process.env.NEXT_PUBLIC_API_BASE_URL, "http://localhost:8000"),
  useEmulators,
  authEmulatorUrl: optional(process.env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_URL, "http://127.0.0.1:9099"),
  firebase: useEmulators
    ? {
        apiKey: "demo-api-key",
        authDomain: `${EMULATOR_PROJECT_ID}.firebaseapp.com`,
        projectId: EMULATOR_PROJECT_ID,
        storageBucket: `${EMULATOR_PROJECT_ID}.appspot.com`,
        messagingSenderId: "",
        appId: "demo-app",
      }
    : {
        apiKey: optional(process.env.NEXT_PUBLIC_FIREBASE_API_KEY),
        authDomain: optional(process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN),
        projectId: optional(process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID),
        storageBucket: optional(process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET),
        messagingSenderId: optional(process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID),
        appId: optional(process.env.NEXT_PUBLIC_FIREBASE_APP_ID),
      },
} as const;

export const isFirebaseConfigured = Boolean(env.firebase.apiKey && env.firebase.projectId);
