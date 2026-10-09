#!/usr/bin/env bash
# Runs the API against local Firebase emulators (start them first: see README).
set -euo pipefail
cd "$(dirname "$0")/.."
FIREBASE_USE_EMULATORS=true exec .venv/bin/uvicorn app.main:app --reload --port 8000
