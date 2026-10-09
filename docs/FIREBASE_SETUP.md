# Configuring Firebase

There are two ways to run VyaparAI locally:

- **A. Emulators (recommended for development).** Everything runs on your machine. No credentials, no real users or data.
- **B. Your real Firebase project** (`avinya-7784e`). Needs a one-time console setup and a service-account key for the backend.

Prerequisites: Node 20+, Python 3.11+, Java 11+ (for emulators), and the Firebase CLI (`npm i -g firebase-tools`).

---

## A. Local emulators

Three terminals, from the repo root:

```bash
firebase emulators:start --only auth,firestore,storage --project demo-vyaparai
```
```bash
cd backend && FIREBASE_USE_EMULATORS=true .venv/bin/uvicorn app.main:app --reload --port 8000
```
```bash
cd frontend && npm run dev:emulators
```

Open http://localhost:3000 and create an account. Emulator UI (users, Firestore data, files): http://localhost:4000.
`demo-vyaparai` is a special "demo" project ID, so the emulators can never touch a real project.

---

## B. Real Firebase project

### 1. Firebase console (one-time)
1. **Authentication → Sign-in method:** enable **Email/Password** and **Google**.
2. **Authentication → Settings → Authorized domains:** `localhost` is there by default. Add your Vercel domain when you deploy.
3. **Firestore Database:** create it in **production mode** (region e.g. `asia-south1`, Mumbai). Production mode starts with deny-all; our rules are deployed next.
4. **Storage:** create the default bucket (same region). The bucket name should be `avinya-7784e.firebasestorage.app`.

### 2. Deploy security rules and indexes
```bash
firebase login
```
```bash
firebase deploy --only firestore:rules,firestore:indexes,storage --project avinya-7784e
```
The Storage rules read Firestore to check membership. If the CLI asks to grant Storage permission to read Firestore, accept.

### 3. Frontend config (public)
`frontend/.env.local` already contains your web app config. Firebase web config is **not secret**: access is controlled by Auth, rules and the backend. The file is git-ignored anyway.
Analytics from the console snippet is intentionally not included; it isn't needed and would add cookies/consent requirements.

### 4. Backend credentials (secret)
1. Console → **Project settings → Service accounts → Generate new private key**.
2. Save it **outside the repository**, for example:
   ```bash
   mkdir -p ~/.config/vyaparai && mv ~/Downloads/avinya-7784e-firebase-adminsdk-*.json ~/.config/vyaparai/firebase-admin.json && chmod 600 ~/.config/vyaparai/firebase-admin.json
   ```
3. Set the path in `backend/.env` (git-ignored):
   ```
   GOOGLE_APPLICATION_CREDENTIALS=/Users/<you>/.config/vyaparai/firebase-admin.json
   ```
   `FIREBASE_PROJECT_ID` and `FIREBASE_STORAGE_BUCKET` are already filled in.

Never commit this key, paste it into chat or tickets, or put it in any `NEXT_PUBLIC_*` variable. If it leaks, delete the key in Google Cloud Console → IAM → Service accounts → Keys.

### 5. Run
```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
```
```bash
cd frontend && npm run dev
```

If the key is missing, protected API calls return `503 server_credentials_missing` and the app shows a clear error. `/api/v1/health` still works.

---

## Production (later)

- **Cloud Run:** don't use a key file. Attach a service account with *Firebase Authentication Admin*, *Cloud Datastore User* and *Storage Object Admin* roles. Leave `GOOGLE_APPLICATION_CREDENTIALS` empty. Set `FIREBASE_PROJECT_ID`, `FIREBASE_STORAGE_BUCKET`, `APP_ENV=production`, `LOG_JSON=true`, and `CORS_ORIGINS=https://<your-vercel-domain>`.
- **Vercel:** set the `NEXT_PUBLIC_FIREBASE_*` variables and `NEXT_PUBLIC_API_BASE_URL` to the Cloud Run URL.
- The backend refuses to start with `FIREBASE_USE_EMULATORS=true` when `APP_ENV=production`.

## Tests

```bash
cd backend && .venv/bin/pytest tests/unit
```
```bash
cd backend && ./scripts/test_integration.sh
```
```bash
cd firebase && npm install && npm test
```
The last two start the emulators automatically.
