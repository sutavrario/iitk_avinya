import { getApp, getApps, initializeApp, type FirebaseApp } from "firebase/app";
import { connectAuthEmulator, getAuth, type Auth } from "firebase/auth";
import { env, isFirebaseConfigured } from "@/lib/env";

/**
 * Client-side Firebase. The browser only uses Firebase Authentication; all data access goes
 * through the FastAPI backend, which verifies the ID token and checks business membership.
 */
let auth: Auth | null = null;

export class FirebaseNotConfiguredError extends Error {
  constructor() {
    super("Firebase is not configured. Copy frontend/.env.example to .env.local and fill it in.");
    this.name = "FirebaseNotConfiguredError";
  }
}

function getFirebaseApp(): FirebaseApp {
  if (!isFirebaseConfigured) throw new FirebaseNotConfiguredError();
  return getApps().length ? getApp() : initializeApp(env.firebase);
}

export function getFirebaseAuth(): Auth {
  if (auth) return auth;
  auth = getAuth(getFirebaseApp());
  if (env.useEmulators) {
    connectAuthEmulator(auth, env.authEmulatorUrl, { disableWarnings: true });
  }
  return auth;
}
