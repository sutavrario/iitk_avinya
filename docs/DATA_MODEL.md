# Data model & access control

All data lives in Cloud Firestore (top-level collections) and Cloud Storage (original uploads).

## Who can do what

| Layer | Enforces |
|---|---|
| **FastAPI** (Admin SDK) | Verifies the Firebase ID token on every protected route (signature, expiry, project, **revocation**). For business routes, takes `businessId` **from the URL only** and loads `businessMembers/{businessId}_{uid}`; no membership → `404` (same as a non-existent business, so IDs can't be probed); insufficient role → `403`. Every write stamps `businessId`/`createdBy` from that check. Request bodies reject unknown fields, so a client can't send `businessId`, `role`, `ownerUid`, etc. |
| **Firestore rules** | Clients may **read** only their own `users/{uid}`, their own memberships, and records of businesses they're a member of. **All client writes are denied.** |
| **Storage rules** | Clients may **read** files under `businesses/{businessId}/…` only if they're a member. **All client writes are denied** (uploads go through the API, which validates type/size/content). |

The browser uses Firebase **only for Authentication**; all data goes through the API.

## Roles

`owner` > `admin` > `member` > `viewer`

| Action | Minimum role |
|---|---|
| Read business, dashboard, records, documents | viewer |
| Create invoices/payments, upload/delete documents | member |
| Edit business profile | admin |
| (future) manage members, delete business | owner |

## Collections

Common fields on every **business-owned** document: `businessId` (string, required), `createdBy` (uid), `createdAt`, `updatedAt` (timestamps).
Money is stored as **integer paise** (`amountPaise`) to avoid rounding errors; the API converts to rupees. Dates are ISO `YYYY-MM-DD` strings.

| Collection | Doc ID | Key fields |
|---|---|---|
| `users` | `{uid}` | `email`, `emailVerified`, `displayName`, `defaultBusinessId`, `preferences{interfaceLanguage, copilotLanguage, alwaysTranslateReplies, showOriginalAlongsideTranslation, numberFormat}` |
| `businesses` | auto | `businessName`, `industry`, `businessType`, `location{city,state,pincode}`, `currency` (`INR`), `financialYearStart` (`april`\|`january`), `paymentTermsDays`, `goals[]`, `preferredLanguage`, `gstin`, `ownerUid` |
| `businessMembers` | `{businessId}_{uid}` | `businessId`, `uid`, `role` — deterministic ID so rules can check membership with one `exists()` |
| `invoices` | manual: auto; imported: `{documentId}_{rowId}` | `businessId`, `invoiceNumber`, `customerName`, `issueDate`, `dueDate` (nullable), `amountPaise`, `gstAmountPaise`, `status` (`unpaid`\|`partially_paid`\|`paid`\|`unknown`; **overdue is derived** on read), `source` (`manual`\|`upload`), plus the normalized fields `recordType`, `counterpartyName`, `currency`, `subtotalPaise`, `taxPaise`, `totalPaise`, `paymentStatus`, `documentPaymentStatus`, `paymentReferences`, `documentId`, `sourceRef`, `extraction`, `dedupeKey` |
| `payments` | auto | `businessId`, `date`, `partyName`, `direction` (`received`\|`paid`), `amountPaise`, `method`, `reference`, `invoiceNumber`, `source` |
| `customers` | auto | `businessId`, `name`, `phone`, `email`, `gstin`, `address` *(defined; endpoints come with the customers feature)* |
| `suppliers` | auto | `businessId`, `name`, `phone`, `email`, `gstin` *(defined)* |
| `expenses` | `{documentId}_{rowId}` | Purchase bills confirmed from documents: `businessId`, `supplierName`, `date`, `dueDate`, plus the same normalized fields as invoices |
| `uploadedDocuments` | auto | `businessId`, `createdBy`, `fileName` (display only), `extension`, `sizeBytes`, `kind`, `contentType` (server-detected), `sha256`, `storagePath`, `recordType`, `status` (`queued`→`processing`→`needs_mapping`\|`needs_review`→`completed`, or `failed`), `processing{run, attempts, errorCode, errorMessage, retryable, method, ocrPages}`, `extraction{columns, mapping, warnings, rowCount, …}`, `confirmedCount`, `duplicateOfDocumentId`, `uploadedAt`. Subcollection `extractedRecords/row00000…` holds draft rows (`businessId`, `run`, `input`, `raw`, `values`, `issues`, `source`, `dedupeKey`, `excluded`, `allowDuplicate`, `confirmedRecordId`). See [INGESTION.md](INGESTION.md) |
| `ingestionJobs` | `{documentId}` | `businessId`, `run`, `status`, `attempts`, `leaseExpiresAt`, `options` |
| `conversations` | auto | `businessId`, `title`, `language`, `updatedAt`; subcollection `messages/{id}` with `businessId`, `role`, `content`, `createdAt` *(defined; used when the AI copilot is integrated)* |
| `actionPlans` | auto | `businessId`, `title`, `items[]`, `status`, `sourceConversationId` *(defined)* |

Storage path for originals: `businesses/{businessId}/documents/{documentId}/original.{ext}` — built only from server-generated IDs; the user's filename is metadata.

Composite indexes for `businessId + date` queries are in `firebase/firestore.indexes.json`.
