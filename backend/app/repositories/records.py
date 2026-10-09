"""Generic access to business-owned collections.

Every function takes a `BusinessAccess` (produced only by the authorization dependency), and
the `businessId` written to or matched in Firestore always comes from it — never from the
request body.
"""

from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import Query
from google.cloud.firestore_v1 import FieldFilter

from app.core.errors import NotFoundError
from app.repositories import collections as col
from app.services.authorization import BusinessAccess

MAX_LIST = 1000


def _check_collection(collection: str) -> None:
    if collection not in col.BUSINESS_OWNED:
        raise ValueError(f"{collection} is not a business-owned collection")


def list_records(
    db: FirestoreClient,
    collection: str,
    access: BusinessAccess,
    order_by: str,
    limit: int = MAX_LIST,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    _check_collection(collection)
    query = (
        db.collection(collection)
        .where(filter=FieldFilter("businessId", "==", access.business_id))
    )
    if filters:
        for k, v in filters.items():
            query = query.where(filter=FieldFilter(k, "==", v))
    query = query.order_by(order_by, direction=Query.DESCENDING).limit(limit)
    return [{**(s.to_dict() or {}), "id": s.id} for s in query.stream()]


def create_record(
    db: FirestoreClient,
    collection: str,
    access: BusinessAccess,
    data: dict[str, Any],
    record_id: str | None = None,
) -> dict[str, Any]:
    _check_collection(collection)
    now = datetime.now(UTC)
    doc = {
        **data,
        # Server-owned fields last so they can't be overridden by `data`.
        "businessId": access.business_id,
        "createdBy": access.user.uid,
        "createdAt": now,
        "updatedAt": now,
    }
    ref = (
        db.collection(collection).document(record_id)
        if record_id
        else db.collection(collection).document()
    )
    ref.set(doc)
    return {**doc, "id": ref.id}


def get_record(
    db: FirestoreClient, collection: str, access: BusinessAccess, record_id: str
) -> dict[str, Any]:
    _check_collection(collection)
    snap = db.collection(collection).document(record_id).get()
    data = snap.to_dict() if snap.exists else None
    # A record of another business is indistinguishable from a missing one.
    if not data or data.get("businessId") != access.business_id:
        raise NotFoundError("Record not found.")
    return {**data, "id": snap.id}


def delete_record(
    db: FirestoreClient, collection: str, access: BusinessAccess, record_id: str
) -> None:
    get_record(db, collection, access, record_id)  # authorization check
    db.collection(collection).document(record_id).delete()
