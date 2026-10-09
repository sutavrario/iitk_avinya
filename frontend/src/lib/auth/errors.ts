import { FirebaseError } from "firebase/app";

const MESSAGES: Record<string, string> = {
  "auth/invalid-credential": "Email or password is incorrect.",
  "auth/wrong-password": "Email or password is incorrect.",
  "auth/user-not-found": "Email or password is incorrect.",
  "auth/invalid-email": "Enter a valid email address.",
  "auth/email-already-in-use": "An account with this email already exists. Try signing in.",
  "auth/weak-password": "Choose a stronger password (at least 8 characters).",
  "auth/too-many-requests": "Too many attempts. Wait a few minutes and try again.",
  "auth/network-request-failed": "Can't reach the sign-in service. Check your internet connection.",
  "auth/user-disabled": "This account has been disabled. Contact support.",
  "auth/popup-closed-by-user": "The Google sign-in window was closed before finishing.",
  "auth/popup-blocked": "Your browser blocked the sign-in pop-up. Allow pop-ups and try again.",
  "auth/cancelled-popup-request": "Sign-in was cancelled.",
  "auth/operation-not-allowed": "This sign-in method isn't enabled for this app yet.",
  "auth/unauthorized-domain": "This website isn't authorised for sign-in. Add it in Firebase Authentication settings.",
  "auth/missing-password": "Enter your password.",
};

/** Turns Firebase Auth errors into friendly messages without leaking internals. */
export function authErrorMessage(error: unknown): string {
  if (error instanceof FirebaseError) {
    return MESSAGES[error.code] ?? "Something went wrong while signing in. Please try again.";
  }
  if (error instanceof Error && error.name === "FirebaseNotConfiguredError") return error.message;
  return "Something went wrong. Please try again.";
}

/** Errors the user caused by dismissing a dialog — don't show them as failures. */
export function isUserCancellation(error: unknown): boolean {
  return (
    error instanceof FirebaseError &&
    (error.code === "auth/popup-closed-by-user" || error.code === "auth/cancelled-popup-request")
  );
}
