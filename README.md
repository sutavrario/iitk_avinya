# VyaparAI

AI copilot for Indian MSMEs. Hackathon project.

- `frontend/` — Next.js (App Router, TypeScript strict, Tailwind, shadcn/ui, Recharts) → Vercel
- `backend/` — FastAPI + Pydantic (Firebase, Gemini, ChromaDB, Translation) → Cloud Run
- `firebase/` — Firestore & Storage security rules, indexes, rules tests
- `docs/` — [project plan](docs/PROJECT_PLAN.md), [conventions](docs/CONVENTIONS.md), [Firebase setup](docs/FIREBASE_SETUP.md), [data model](docs/DATA_MODEL.md), [document ingestion](docs/INGESTION.md)
- `sample_data/` — synthetic demo files; `sample_data/ingestion/` has test documents for every ingestion case

## Prerequisites
- Node.js 20+ and npm
- Python 3.11+
- Java 11+ and Firebase CLI (`npm i -g firebase-tools`) for local emulators
- Tesseract for OCR of scanned PDFs/photos (`brew install tesseract`); optional

## Run locally

Quickest path, no cloud credentials needed: run against the Firebase emulators. Real-project setup is in [docs/FIREBASE_SETUP.md](docs/FIREBASE_SETUP.md).

One-time setup:
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && cp .env.example .env
```
```bash
cd frontend && npm install && cp .env.example .env.local
```

Then, in three terminals from the repo root:
```bash
firebase emulators:start --only auth,firestore,storage --project demo-vyaparai
```
```bash
cd backend && FIREBASE_USE_EMULATORS=true .venv/bin/uvicorn app.main:app --reload --port 8000
```
```bash
cd frontend && npm run dev:emulators
```
Open http://localhost:3000 and create an account. Emulator UI: http://localhost:4000. API docs: http://localhost:8000/docs.

## Quality checks
```bash
cd backend && .venv/bin/pytest tests/unit && .venv/bin/ruff check . && .venv/bin/mypy app
cd backend && ./scripts/test_integration.sh          # API + Auth/Firestore/Storage emulators
cd firebase && npm install && npm test               # security rules
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Deploy (later)
- Backend: `gcloud run deploy vyaparai-api --source backend` (uses `backend/Dockerfile`).
- Frontend: import repo in Vercel with root directory `frontend`, set `NEXT_PUBLIC_*` vars.
