#!/usr/bin/env bash
# Runs backend integration tests against local Firebase emulators (no real project touched).
set -euo pipefail
cd "$(dirname "$0")/../.."
firebase emulators:exec --only auth,firestore,storage --project demo-vyaparai \
  "cd backend && FIREBASE_USE_EMULATORS=true APP_ENV=test .venv/bin/pytest tests/integration -q $*"
