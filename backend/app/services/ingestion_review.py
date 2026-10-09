"""Review and confirmation of extracted rows."""

from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1 import FieldFilter

from app.core.errors import ConflictError, NotFoundError
from app.repositories import collections as col
from app.schemas.ingestion import ConfirmResponse, ConfirmRowResult, RowUpdate
from app.services.authorization import BusinessAccess
from app.services.ingestion_store import (
    TARGET_COLLECTION,
    add_duplicate_issue,
    draft_fields,
    find_existing,
    rebuild,
    record_from_row,
)

REVIEWABLE = {"needs_review", "completed"}


def load_document(db: FirestoreClient, access: BusinessAccess, document_id: str) -> dict[str, Any]:
    snap = db.collection(col.UPLOADED_DOCUMENTS).document(document_id).get()
    data = snap.to_dict() if snap.exists else None
    if not data or data.get("businessId") != access.business_id:
        raise NotFoundError("Document not found.", code="document_not_found")
    return {**data, "id": snap.id}


def _rows_ref(db: FirestoreClient, document_id: str) -> Any:
    return (
        db.collection(col.UPLOADED_DOCUMENTS)
        .document(document_id)
        .collection(col.EXTRACTED_RECORDS)
    )


def list_rows(db: FirestoreClient, doc: dict[str, Any]) -> list[dict[str, Any]]:
    run = (doc.get("processing") or {}).get("run")
    if run is None:
        return []
    query = _rows_ref(db, doc["id"]).where(filter=FieldFilter("run", "==", run))
    rows = [{**(s.to_dict() or {}), "id": s.id} for s in query.stream()]
    return sorted(rows, key=lambda r: r.get("index", 0))


def _record_id(document_id: str, row_id: str) -> str:
    return f"{document_id}_{row_id}"


def update_row(
    db: FirestoreClient, access: BusinessAccess, doc: dict[str, Any], row_id: str, update: RowUpdate
) -> dict[str, Any]:
    if doc.get("status") not in REVIEWABLE:
        raise ConflictError("This document isn't ready for review yet.", code="not_reviewable")
    ref = _rows_ref(db, doc["id"]).document(row_id)
    snap = ref.get()
    row = snap.to_dict() if snap.exists else None
    run = (doc.get("processing") or {}).get("run")
    if not row or row.get("businessId") != access.business_id or row.get("run") != run:
        raise NotFoundError("Row not found.", code="row_not_found")
    if row.get("confirmedRecordId"):
        raise ConflictError(
            "This row is already saved and can't be edited here.", code="already_confirmed"
        )

    edited = set(row.get("editedFields") or [])
    inputs = dict(row.get("input") or {})
    confidence = dict(row.get("inputConfidence") or {})
    for field, value in (update.values or {}).items():
        inputs[field] = value.strip() if isinstance(value, str) and value.strip() else None
        confidence[field] = 1.0  # checked by a person
        edited.add(field)
    row["input"], row["inputConfidence"] = inputs, confidence
    if update.payment_status is not None:
        row["userPaymentStatus"] = update.payment_status
        edited.add("paymentStatus")
    if update.payment_references is not None:
        row["paymentReferences"] = [r.strip() for r in update.payment_references if r.strip()]
        edited.add("paymentReferences")
    if update.excluded is not None:
        row["excluded"] = update.excluded
    if update.allow_duplicate is not None:
        row["allowDuplicate"] = update.allow_duplicate
    # Edited dates come from a date picker in ISO format, so the column's dd/mm order no longer applies.
    if update.values and ({"invoiceDate", "dueDate"} & set(update.values)):
        row["dateOrders"] = {
            k: v for k, v in (row.get("dateOrders") or {}).items() if k not in update.values
        }

    record_type = doc.get("recordType", "sales_invoice")
    draft = rebuild(row, record_type, datetime.now(UTC).date())
    fields = draft_fields(draft)
    if draft.dedupe_key:
        existing = find_existing(db, access.business_id, record_type, [draft.dedupe_key])
        if draft.dedupe_key in existing:
            fields["issues"] = add_duplicate_issue(
                fields["issues"], existing[draft.dedupe_key], _record_id(doc["id"], row_id)
            )
    row.update(fields)
    row["editedFields"] = sorted(edited)
    row["updatedAt"] = datetime.now(UTC)
    row["updatedBy"] = access.user.uid
    ref.set({k: v for k, v in row.items() if k != "id"})
    return {**row, "id": row_id}


def confirm(
    db: FirestoreClient, access: BusinessAccess, doc: dict[str, Any], row_ids: list[str] | None
) -> ConfirmResponse:
    if doc.get("status") not in REVIEWABLE:
        raise ConflictError("This document isn't ready to confirm.", code="not_reviewable")
    rows = list_rows(db, doc)
    by_id = {r["id"]: r for r in rows}
    targets = row_ids if row_ids is not None else [r["id"] for r in rows if not r.get("excluded")]
    collection = TARGET_COLLECTION[doc.get("recordType", "sales_invoice")]
    results: list[ConfirmRowResult] = []

    for row_id in targets:
        row = by_id.get(row_id)
        if row is None:
            raise NotFoundError(f"Row {row_id} not found.", code="row_not_found")
        if row.get("excluded"):
            results.append(ConfirmRowResult(row_id=row_id, outcome="excluded"))
            continue
        if row.get("hasErrors"):
            results.append(
                ConfirmRowResult(
                    row_id=row_id,
                    outcome="has_errors",
                    message="Fix the highlighted problems first.",
                )
            )
            continue
        results.append(_confirm_row(db, access, doc, row, collection))

    status = _refresh_document(db, doc["id"])
    return ConfirmResponse(
        results=results,
        created=sum(r.outcome == "created" for r in results),
        document_status=status,
    )


def _confirm_row(
    db: FirestoreClient,
    access: BusinessAccess,
    doc: dict[str, Any],
    row: dict[str, Any],
    collection: str,
) -> ConfirmRowResult:
    row_ref = _rows_ref(db, doc["id"]).document(row["id"])
    record_id = _record_id(doc["id"], row["id"])
    record_ref = db.collection(collection).document(record_id)
    key = row.get("dedupeKey")

    @firestore.transactional
    def txn(tx: Any) -> ConfirmRowResult:
        current = row_ref.get(transaction=tx).to_dict() or {}
        if current.get("confirmedRecordId"):
            return ConfirmRowResult(
                row_id=row["id"],
                outcome="already_confirmed",
                record_id=current["confirmedRecordId"],
            )
        if key and not current.get("allowDuplicate"):
            dup_query = (
                db.collection(collection)
                .where(filter=FieldFilter("businessId", "==", access.business_id))
                .where(filter=FieldFilter("dedupeKey", "==", key))
                .limit(2)
            )
            others = [s.id for s in dup_query.get(transaction=tx) if s.id != record_id]
            if others:
                return ConfirmRowResult(
                    row_id=row["id"],
                    outcome="duplicate",
                    record_id=others[0],
                    message="Already saved. Mark it as not a duplicate to save it anyway.",
                )
        now = datetime.now(UTC)
        tx.set(record_ref, record_from_row(current | {"id": row["id"]}, doc, access.user.uid, now))
        tx.update(
            row_ref,
            {
                "confirmedRecordId": record_id,
                "confirmedCollection": collection,
                "confirmedAt": now,
                "updatedAt": now,
            },
        )
        return ConfirmRowResult(row_id=row["id"], outcome="created", record_id=record_id)

    result: ConfirmRowResult = txn(db.transaction())
    return result


def _refresh_document(db: FirestoreClient, document_id: str) -> str:
    doc_ref = db.collection(col.UPLOADED_DOCUMENTS).document(document_id)
    doc = {**(doc_ref.get().to_dict() or {}), "id": document_id}
    rows = list_rows(db, doc)
    confirmed = sum(1 for r in rows if r.get("confirmedRecordId"))
    open_rows = [r for r in rows if not r.get("excluded") and not r.get("confirmedRecordId")]
    status = "completed" if rows and not open_rows else "needs_review"
    doc_ref.update({"confirmedCount": confirmed, "status": status, "updatedAt": datetime.now(UTC)})
    return status
