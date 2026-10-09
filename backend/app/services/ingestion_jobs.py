"""Background ingestion jobs with safe retries.

Idempotency design:
- One job document per uploaded document (`ingestionJobs/{documentId}`) with a monotonically
  increasing `run`. Enqueueing bumps `run`; a worker only processes the run it was given and
  only if it can claim it (status queued, or running with an expired lease).
- Draft rows have deterministic IDs and carry `run`; readers only see rows of the current run.
- Confirmed records get deterministic IDs (`{documentId}_{rowId}`), so confirming twice
  can't create two records. Re-processing is blocked once any row is confirmed.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from google.cloud import firestore
from google.cloud.firestore import Client as FirestoreClient

from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.core.firebase import get_bucket, get_db
from app.core.logging import get_logger
from app.ingestion.errors import IngestionError
from app.ingestion.pipeline import ExtractionOptions, ExtractionOutcome, run_extraction
from app.repositories import collections as col
from app.services.authorization import BusinessAccess
from app.services.ingestion_store import (
    add_duplicate_issue,
    draft_fields,
    find_existing,
    input_strings,
    providers,
)

logger = get_logger(__name__)
_BATCH = 400


def _now() -> datetime:
    return datetime.now(UTC)


def _doc_ref(db: FirestoreClient, document_id: str) -> Any:
    return db.collection(col.UPLOADED_DOCUMENTS).document(document_id)


def _job_ref(db: FirestoreClient, document_id: str) -> Any:
    return db.collection(col.INGESTION_JOBS).document(document_id)


def enqueue(
    db: FirestoreClient, access: BusinessAccess, document_id: str, options: dict[str, Any]
) -> int:
    """Queue a (re)processing run. Returns the run number to hand to `run_job`."""
    lease = timedelta(seconds=get_settings().ingestion_lease_seconds)
    doc_ref, job_ref = _doc_ref(db, document_id), _job_ref(db, document_id)

    @firestore.transactional
    def txn(tx: Any) -> int:
        doc_snap = doc_ref.get(transaction=tx)
        doc = doc_snap.to_dict() if doc_snap.exists else None
        if not doc or doc.get("businessId") != access.business_id:
            raise NotFoundError("Document not found.", code="document_not_found")
        if doc.get("confirmedCount", 0) > 0:
            raise ConflictError(
                "Some records from this document are already saved, so it can't be re-processed.",
                code="already_confirmed",
            )
        job_snap = job_ref.get(transaction=tx)
        job = job_snap.to_dict() if job_snap.exists else {}
        now = _now()
        if (
            job.get("status") in {"queued", "running"}
            and job.get("leaseExpiresAt")
            and job["leaseExpiresAt"] > now
        ):
            raise ConflictError(
                "This document is already being processed.", code="already_processing"
            )
        run = int(job.get("run", 0)) + 1
        tx.set(
            job_ref,
            {
                "businessId": access.business_id,
                "documentId": document_id,
                "status": "queued",
                "run": run,
                "attempts": int(job.get("attempts", 0)),
                "options": options,
                "requestedBy": access.user.uid,
                "leaseExpiresAt": now + lease,
                "createdAt": job.get("createdAt", now),
                "updatedAt": now,
            },
        )
        tx.update(
            doc_ref,
            {
                "status": "queued",
                "processing.run": run,
                "processing.errorCode": None,
                "processing.errorMessage": None,
                "processing.retryable": False,
                "updatedAt": now,
            },
        )
        return run

    run: int = txn(db.transaction())
    return run


def run_job(business_id: str, document_id: str, run: int) -> None:
    """Entry point for the background worker. Safe to call more than once for the same run."""
    db = get_db()
    if not _claim(db, document_id, run):
        logger.info(
            "Skipping ingestion run %s for %s (superseded or already running)", run, document_id
        )
        return
    try:
        doc = _doc_ref(db, document_id).get().to_dict() or {}
        if doc.get("businessId") != business_id:
            raise IngestionError("document_not_found", "The document no longer exists.")
        job = _job_ref(db, document_id).get().to_dict() or {}
        content = get_bucket().blob(doc["storagePath"]).download_as_bytes()
        if doc.get("sha256") and hashlib.sha256(content).hexdigest() != doc["sha256"]:
            raise IngestionError(
                "integrity_error", "The stored file doesn't match what was uploaded."
            )
        outcome = _extract(content, doc, job.get("options") or {})
        _save_outcome(db, {**doc, "id": document_id}, run, outcome)
    except IngestionError as exc:
        logger.warning("Ingestion of %s failed: %s", document_id, exc.code)
        _fail(db, document_id, run, exc.code, exc.message, exc.retryable)
    except Exception:
        logger.exception("Ingestion of %s crashed", document_id)
        _fail(
            db,
            document_id,
            run,
            "internal_error",
            "Something went wrong while reading this file. Please try again.",
            True,
        )


def _claim(db: FirestoreClient, document_id: str, run: int) -> bool:
    lease = timedelta(seconds=get_settings().ingestion_lease_seconds)
    job_ref, doc_ref = _job_ref(db, document_id), _doc_ref(db, document_id)

    @firestore.transactional
    def txn(tx: Any) -> bool:
        snap = job_ref.get(transaction=tx)
        job = snap.to_dict() if snap.exists else None
        now = _now()
        if not job or job.get("run") != run:
            return False
        stale_running = (
            job.get("status") == "running"
            and job.get("leaseExpiresAt")
            and job["leaseExpiresAt"] <= now
        )
        if job.get("status") != "queued" and not stale_running:
            return False
        tx.update(
            job_ref,
            {
                "status": "running",
                "attempts": int(job.get("attempts", 0)) + 1,
                "leaseExpiresAt": now + lease,
                "startedAt": now,
                "updatedAt": now,
            },
        )
        tx.update(
            doc_ref,
            {
                "status": "processing",
                "processing.attempts": int(job.get("attempts", 0)) + 1,
                "processing.startedAt": now,
                "updatedAt": now,
            },
        )
        return True

    claimed: bool = txn(db.transaction())
    return claimed


def _extract(content: bytes, doc: dict[str, Any], options: dict[str, Any]) -> ExtractionOutcome:
    settings = get_settings()
    ocr, extractor = providers(settings)
    return run_extraction(
        content,
        # Documents uploaded before ingestion existed have no "extension" field.
        extension=doc.get("extension") or "." + str(doc["storagePath"]).rsplit(".", 1)[-1],
        options=ExtractionOptions(
            record_type=doc.get("recordType", "sales_invoice"),
            column_mapping=options.get("columnMapping"),
            sheet_name=options.get("sheetName"),
            pdf_strategy="ocr" if options.get("forceOcr") else settings.pdf_text_strategy,
        ),
        ocr=ocr,
        extractor=extractor,
        today=_now().date(),
    )


def _is_current(db: FirestoreClient, document_id: str, run: int) -> bool:
    job = _job_ref(db, document_id).get().to_dict() or {}
    return bool(job.get("run") == run and job.get("status") == "running")


def _save_outcome(
    db: FirestoreClient, doc: dict[str, Any], run: int, outcome: ExtractionOutcome
) -> None:
    document_id, business_id = doc["id"], doc["businessId"]
    if not _is_current(db, document_id, run):
        return  # a newer run was requested; drop these results
    rows_ref = _doc_ref(db, document_id).collection(col.EXTRACTED_RECORDS)
    now = _now()

    existing = find_existing(
        db,
        business_id,
        doc.get("recordType", "sales_invoice"),
        (r.draft.dedupe_key or "" for r in outcome.rows),
    )
    new_rows: dict[str, dict[str, Any]] = {}
    for r in outcome.rows:
        fields = draft_fields(r.draft)
        if r.draft.dedupe_key in existing:
            fields["issues"] = add_duplicate_issue(
                fields["issues"], existing[r.draft.dedupe_key], None
            )
        new_rows[r.row_id] = {
            "businessId": business_id,
            "documentId": document_id,
            "run": run,
            "index": r.index,
            "input": input_strings({**r.draft.raw}),
            "inputConfidence": r.draft.field_confidence,
            "raw": r.draft.raw,
            "dateOrders": r.date_orders,
            "paymentReferences": r.draft.values.payment_references,
            "userPaymentStatus": None,
            "source": r.source.to_dict(),
            "excluded": False,
            "allowDuplicate": False,
            "editedFields": [],
            "confirmedRecordId": None,
            **fields,
            "createdAt": now,
            "updatedAt": now,
        }

    # Replace rows from earlier runs. Deterministic IDs make this idempotent.
    stale = [s.reference for s in rows_ref.stream() if s.id not in new_rows]
    writes: list[tuple[Any, dict[str, Any] | None]] = [(ref, None) for ref in stale]
    writes += [(rows_ref.document(rid), data) for rid, data in new_rows.items()]
    for i in range(0, len(writes), _BATCH):
        batch = db.batch()
        for ref, data in writes[i : i + _BATCH]:
            if data is None:
                batch.delete(ref)
            else:
                batch.set(ref, data)
        batch.commit()

    extraction = {
        "sheetName": outcome.sheet_name,
        "sheetNames": outcome.sheet_names,
        "columns": outcome.columns,
        "sampleRows": outcome.sample_rows,
        "headerRowNumber": outcome.header_row_number,
        "mapping": outcome.mapping,
        "mappingConfidence": outcome.mapping_confidence,
        "warnings": [w.to_dict() for w in outcome.warnings],
        "rowCount": len(new_rows),
        "errorRowCount": sum(1 for r in new_rows.values() if r["hasErrors"]),
    }
    _finish(
        db,
        document_id,
        run,
        outcome.status,
        extraction,
        {"method": outcome.method, "ocrPages": outcome.ocr_pages},
    )


def _finish(
    db: FirestoreClient,
    document_id: str,
    run: int,
    status: str,
    extraction: dict[str, Any],
    processing: dict[str, Any],
) -> None:
    job_ref, doc_ref = _job_ref(db, document_id), _doc_ref(db, document_id)

    @firestore.transactional
    def txn(tx: Any) -> None:
        job = job_ref.get(transaction=tx).to_dict() or {}
        if job.get("run") != run:
            return
        now = _now()
        tx.update(
            job_ref,
            {"status": "succeeded", "leaseExpiresAt": None, "finishedAt": now, "updatedAt": now},
        )
        tx.update(
            doc_ref,
            {
                "status": status,
                "extraction": extraction,
                "processing.method": processing["method"],
                "processing.ocrPages": processing["ocrPages"],
                "processing.finishedAt": now,
                "updatedAt": now,
            },
        )

    txn(db.transaction())


def _fail(
    db: FirestoreClient, document_id: str, run: int, code: str, message: str, retryable: bool
) -> None:
    job_ref, doc_ref = _job_ref(db, document_id), _doc_ref(db, document_id)

    @firestore.transactional
    def txn(tx: Any) -> None:
        job = job_ref.get(transaction=tx).to_dict() or {}
        if job.get("run") != run:
            return
        now = _now()
        tx.update(
            job_ref,
            {
                "status": "failed",
                "leaseExpiresAt": None,
                "lastError": code,
                "finishedAt": now,
                "updatedAt": now,
            },
        )
        tx.update(
            doc_ref,
            {
                "status": "failed",
                "processing.errorCode": code,
                "processing.errorMessage": message,
                "processing.retryable": retryable,
                "processing.finishedAt": now,
                "updatedAt": now,
            },
        )

    try:
        txn(db.transaction())
    except Exception:  # pragma: no cover - best effort; the lease will expire and allow a retry
        logger.exception("Couldn't record failure for %s", document_id)
