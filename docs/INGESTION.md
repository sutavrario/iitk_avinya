# Document ingestion

Turns uploaded spreadsheets, PDFs and photos into **reviewed** invoice / expense records.
Nothing is saved as a business record until a person has checked it.

```
Upload ─▶ Cloud Storage (private original) + uploadedDocuments record + ingestionJobs/{docId}
             │  background task (FastAPI BackgroundTasks; swap for Cloud Tasks later)
             ▼
        Parse ─▶ Extract ─▶ Normalize ─▶ Validate ─▶ duplicate check
             │
             ├─ needs_mapping  → user matches spreadsheet columns → re-run
             └─ needs_review   → user fixes / skips rows → Confirm
                                                          ▼
                                       invoices (sales) / expenses (purchases)
```

## Supported inputs

| Type | How it's read | Library |
|---|---|---|
| `.csv` | Encoding (UTF-8/Windows-1252) and delimiter (`, ; tab \|`) auto-detected | pandas |
| `.xlsx` | First non-empty sheet (or chosen sheet); zip-bomb and structure checks first | pandas + openpyxl |
| `.xls` | Legacy Excel | pandas + xlrd |
| Digital PDF | Embedded text layer | pypdfium2 (no PyMuPDF) |
| Scanned PDF / photo | Pages rendered at 300 DPI, then OCR | pypdfium2 + **Tesseract** |

`PDF_TEXT_STRATEGY=auto` uses the text layer and OCRs only pages with no text; `ocr` forces OCR.
The UI also offers "Try again with OCR" per document.

## Pipeline stages (`backend/app/ingestion/`, pure functions, no Firebase)

1. **Parse.** `spreadsheet.py` finds the header row (even below title rows), skips "Total" rows and suggests a **column mapping** with confidence. Columns are scored by header synonyms (e.g. *Voucher No.*, *Party A/c Name*, *Taxable Amt*, *CGST/SGST/IGST*) and by whether the values fit (dates and amounts). If a required field is unmapped or uncertain, the document goes to `needs_mapping`. `pdf.py` and `ocr.py` produce page text.
2. **Extract.** Spreadsheet rows map directly. Text goes through an `ExtractionProvider`: the built-in `RuleBasedExtractor` (free; GST invoice labels), or `LlmExtractionProvider` (placeholder for Gemini; falls back to rules until configured).
3. **Normalize + validate** (`drafts.py`). The same code runs for extracted values and for the user's edits:
   - Amounts like `₹1,23,456.00`, `Rs. 500/-` and `(1,200)` become exact decimals. A blank stays **null**; it is never 0.
   - Day/month order is inferred per column ("31/01" proves day-first). Truly ambiguous dates get a warning.
   - Missing currency defaults to INR **with a visible warning**. Non-INR amounts are kept separate from ₹ totals.
   - Errors (block saving): a required field is missing (invoice no., party, date, total), an unreadable date or amount, `subtotal + tax ≠ total` (±₹1), due date before invoice date, or tax greater than the total.
   - Warnings: low OCR confidence, future or implausible dates, negative amounts (credit notes), tax missing.
4. **Payment status.** What the document says ("Paid", "Due", "Balance due") is stored as `documentPaymentStatus`, which is *evidence only*. The record's `paymentStatus` stays **`unknown`** until the user chooses. The dashboard reports unconfirmed invoices separately instead of counting them as owed. They can't become "overdue" either, and neither can invoices without a due date.
5. **Duplicates.** The `dedupeKey` is a hash of record type + normalized invoice number + normalized party, scoped by `businessId`. Duplicates are flagged within a file (`duplicate_in_file`) and against saved records (`possible_duplicate`). Confirming one is refused unless the user ticks "this is a different invoice". Re-uploading an identical file is flagged via its SHA-256. Manual invoice entry also returns 409 on duplicates.

## Normalized invoice schema

`invoiceNumber`, `documentId`, `recordType` (`sales_invoice` | `purchase_invoice`), `counterpartyName` (customer or supplier), `invoiceDate`, `dueDate`, `currency`, `subtotal`, `tax`, `total`, `paymentStatus`, `documentPaymentStatus`, `paymentReferences[]`, `confidence`, `fieldConfidence{}`, `issues[]` (`code`, `severity`, `message`, `field`, `suggestedValue`, `relatedRecordId`), `source` (`documentId`, `fileName`, `storagePath`, `method`, `sheetName`, `rowNumber`, `page`, `snippet`).
API amounts are exact decimal strings; Firestore stores integer paise.

## Jobs, retries and idempotency (`services/ingestion_jobs.py`)

- `ingestionJobs/{documentId}` has `run` (incremented on each enqueue), `status`, `attempts` and a **lease**.
- A worker processes only the run it was given and only after claiming it in a transaction (queued, or running with an expired lease). Duplicate or stale deliveries are no-ops.
- Draft rows (`uploadedDocuments/{id}/extractedRecords/row00000…`) have deterministic IDs and a `run` field. A new run replaces them, and readers only see the current run.
- Confirmed records get deterministic IDs (`{documentId}_{rowId}`), and confirmation is transactional. Confirming twice creates nothing new.
- Once any row is confirmed, re-processing and deletion of the document are refused (409). The original stays as the source of those records.
- Failures record `errorCode`, `errorMessage` and `retryable`. "Retry" re-enqueues.

## API (`/api/v1/businesses/{businessId}/documents`)

| Method | Path | |
|---|---|---|
| POST | `` | multipart `file` + `recordType` → stores the original and queues processing (201) |
| GET | `` / `/{id}` | status for polling (`queued → processing → needs_mapping / needs_review → completed`, or `failed`) |
| POST | `/{id}/process` | retry, or re-run with `columnMapping`, `sheetName`, `recordType`, `forceOcr` (202) |
| GET | `/{id}/rows` | draft rows with raw values, issues and confidence |
| PATCH | `/{id}/rows/{rowId}` | corrections, `paymentStatus`, `excluded`, `allowDuplicate`; re-validated by the server |
| POST | `/{id}/confirm` | save rows; per-row outcome `created / already_confirmed / duplicate / has_errors / excluded` |
| GET | `/{id}/file` | the original file, streamed (bucket stays private) |
| DELETE | `/{id}` | only if nothing was saved from it |

All routes require membership of the business in the URL (viewer can read; member+ can upload, edit and confirm).

## Limits & safety

10 MB per file (`MAX_UPLOAD_BYTES`). Extension **and** magic bytes are checked; the server decides the content type. Other limits: 5,000 rows, 100 columns, 30 PDF pages, a 40-megapixel image cap (decompression bombs), 100 MB uncompressed xlsx, a 60 s OCR timeout per page. Password-protected PDFs are rejected with a clear message. The SHA-256 is re-checked before parsing.

## Configuration

```
OCR_PROVIDER=tesseract     # or none
OCR_LANGUAGES=eng          # eng+hin after `brew install tesseract-lang`
TESSERACT_CMD=             # if not on PATH
EXTRACTION_PROVIDER=rules  # llm reserved for Gemini
PDF_TEXT_STRATEGY=auto     # or ocr
```
Install Tesseract with `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` (Debian/Cloud Run image). Without it, spreadsheets and digital PDFs still work; scans fail with `ocr_unavailable`.

## Tests

- `backend/tests/unit/test_ingestion.py` covers the sample files: valid inputs, malformed files, missing fields, incorrect totals, duplicates, OCR paths (fake OCR plus real Tesseract when installed), limits.
- `backend/tests/integration/test_ingestion_flow.py` covers the emulator end-to-end flow: review, corrections, confirm, cross-document duplicates, idempotent retries and duplicate job delivery, column mapping, cross-business access, and viewer role.
