# Conventions

## General
- Monorepo: `frontend/` and `backend/` have **independent** dependencies. Never install frontend packages at root or Python packages globally.
- Small PRs/commits, imperative commit messages (`Add invoice parser`).
- No secrets in source, ever. Config comes from env vars.

## Python (backend)
- Python 3.11+, type hints everywhere; `mypy --strict` and `ruff` must pass.
- Naming: `snake_case` modules/functions, `PascalCase` classes, `UPPER_SNAKE` constants.
- Routers are thin; logic lives in `app/services/`. Request/response bodies are Pydantic models in `app/schemas/`.
- Access settings only via `get_settings()`; never read `os.environ` directly.
- External clients (Gemini, Firestore, …) are created lazily in services so the app boots without credentials.
- Tests in `backend/tests/` with pytest; mock external services.

## TypeScript (frontend)
- `strict` mode; no `any` (use `unknown` + narrowing).
- Components `PascalCase` exports in `kebab-case.tsx` files; hooks `useX`.
- UI primitives from shadcn/ui (`src/components/ui`, add via `npx shadcn@latest add <name>`); charts with Recharts.
- All backend calls go through `src/lib/api-client.ts`; env via `src/lib/env.ts`.
- Server Components by default; add `"use client"` only when needed.

## Frontend structure & data layer
- Routes: `src/app/page.tsx` (landing), `sign-in/`, `onboarding/`, and the signed-in shell in `src/app/(app)/` (dashboard, documents, records, copilot, settings) sharing the sidebar layout.
- Pages are thin; each renders a `*-view.tsx` from `src/components/<feature>/`. Shared pieces live in `components/shared` (DataTable, StatCard, EmptyState, ErrorState, MockDataBanner, StatusBadge), `components/forms` (FormField, SelectField, ChoiceCard), `components/charts`, `components/layout`.
- Domain types: `src/lib/types.ts`. Data access only through `api` from `@/lib/api`, typed by `src/lib/api/contracts.ts`, implemented in `src/lib/api/http.ts` via `apiFetch` (attaches the Firebase ID token, retries once on 401, signs out on revoked sessions).
- Auth: `AuthProvider` (Firebase Auth only) → `RequireAuth` → `WorkspaceProvider` (`/me` + active business) → `RequireBusiness`. Pages inside `(app)` use `useActiveBusiness()` and pass `business.id` to the API. Client guards are UX only — the server and security rules are the real enforcement.
- Only the copilot is still mocked (`src/lib/api/mock/copilot.ts`, `isMock: true`).
- **Mock data must always be labelled** in the UI (`MockDataBanner`, "Sample" badges, `isMock` on dashboard/chat). Never show illustrative figures as the user's real numbers.
- Validation lives in `src/lib/validation/` as pure functions (unit-tested with Vitest); messages say what to do, not just what's wrong.
- Every data view handles loading (skeletons), error (`ErrorState` with retry) and empty (`EmptyState` with a next action).

## Authorization (backend)
- Business-scoped routes live under `/api/v1/businesses/{business_id}/…` and depend on `CanView` / `CanEdit` / `CanAdmin` from `app/services/authorization.py`. Never read a business ID from a body or query string.
- Use `app/repositories/records.py` for business-owned collections: it stamps `businessId`/`createdBy` from the `BusinessAccess` and checks ownership on get/delete.
- Request models extend `InputModel` (`extra="forbid"`). New collections must be added to `firebase/firestore.rules` (read-if-member, no client writes) and covered in `firebase/tests/rules.test.ts`.

## Environment variables
| Where | File | Rules |
|---|---|---|
| Backend | `backend/.env` (from `.env.example`) | `UPPER_SNAKE`, mapped to `Settings` fields in `app/core/config.py`. Secrets typed as `SecretStr`. |
| Frontend | `frontend/.env.local` (from `.env.example`) | Browser-visible vars **must** start with `NEXT_PUBLIC_` and must not be secret. |
| Cloud Run | Service env vars / Secret Manager | `GEMINI_API_KEY` via Secret Manager; credentials via the service account (no JSON key). |
| Vercel | Project env vars | Same names as `frontend/.env.example`. |

Every new variable must be added to the relevant `.env.example` with a comment.

## Error handling
All API errors share one envelope:
```json
{ "error": { "code": "not_found", "message": "Invoice not found", "request_id": "…", "details": null } }
```
- Raise `AppError` subclasses (`NotFoundError`, `UnauthorizedError`, `ExternalServiceError`, …) from `app/core/errors.py`; don't raise bare `HTTPException` in services.
- Unhandled exceptions are logged with stack trace and returned as `500 internal_error` without leaking internals.
- Frontend: `apiFetch` throws `ApiError` (status, code, message, requestId); show `message`, log `requestId`.

## Logging
- Use `get_logger(__name__)`; never `print`.
- Every request gets an `X-Request-ID` (incoming header honoured), included in each log line and the response.
- `LOG_JSON=true` in Cloud Run emits JSON with a `severity` field that Cloud Logging understands.
- Never log secrets, ID tokens, or full document contents / PII.
