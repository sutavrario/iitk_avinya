# VyaparAI — Project Plan

AI copilot for Indian MSMEs: upload business documents (sales sheets, invoices, statements),
get insights, dashboards and answers in English and Indian languages.

## Architecture

```
Next.js (Vercel) ──HTTPS + Firebase ID token──▶ FastAPI (Cloud Run)
     │                                              ├─ Firestore        (business data, metadata)
     └─ Firebase Auth (client sign-in)              ├─ Cloud Storage    (uploaded files)
                                                    ├─ ChromaDB         (document embeddings / RAG)
                                                    ├─ Gemini API       (reasoning, extraction, embeddings)
                                                    └─ Cloud Translation (multilingual I/O)
```

The backend is the only component holding secrets and talking to Gemini/Translation/Admin SDK.
The frontend only uses Firebase's public web config and calls the backend with an ID token.

## Milestones

| # | Milestone | Scope |
|---|-----------|-------|
| 0 | **Foundation** (done) | Monorepo, conventions, health check, error/logging scaffolding |
| 1 | Auth | Firebase sign-in on frontend; backend verifies ID token (dependency `get_current_user`) |
| 2 | Upload & parse | Upload to Cloud Storage; parse CSV/XLSX (pandas/openpyxl), PDF (PyMuPDF), OCR fallback; store normalised rows in Firestore |
| 3 | Insights dashboard | Sales/expense/GST summaries; Recharts dashboard |
| 4 | Copilot chat (RAG) | Chunk + embed docs into ChromaDB; Gemini answers grounded in user data with citations |
| 5 | Multilingual | Translate queries/answers (Hindi, Bengali, Tamil, …) via Cloud Translation |
| 6 | Deploy & demo | Cloud Run + Vercel, seeded demo account, pitch flow |

## Backend layout

- `app/api/v1/` — routers (thin: validate, call service, return schema)
- `app/schemas/` — Pydantic request/response models
- `app/services/` — business logic & external integrations (gemini, firestore, storage, parsing, rag, translation)
- `app/core/` — config, logging, errors, middleware

## Open questions
- ChromaDB in production: Cloud Run filesystem is ephemeral. Options: rebuild index on start from Firestore, mount a GCS volume, or run Chroma as a separate service. Decide at milestone 4.
- OCR engine: Gemini vision vs Tesseract vs Cloud Vision. Gemini vision avoids an extra system dependency.
