from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1 import FieldFilter

from app.core.security import AuthenticatedUser
from app.repositories import collections as col
from app.schemas.user import UserPreferences


def ensure_user(db: FirestoreClient, user: AuthenticatedUser) -> dict[str, Any]:
    """Return the users/{uid} document, creating it on first sign-in."""
    ref = db.collection(col.USERS).document(user.uid)
    snap = ref.get()
    if snap.exists:
        data = snap.to_dict() or {}
        # Keep identity fields in sync with the auth token.
        if data.get("email") != user.email or data.get("emailVerified") != user.email_verified:
            updates = {
                "email": user.email,
                "emailVerified": user.email_verified,
                "updatedAt": datetime.now(UTC),
            }
            ref.update(updates)
            data.update(updates)
        return data
    now = datetime.now(UTC)
    data = {
        "uid": user.uid,
        "email": user.email,
        "emailVerified": user.email_verified,
        "displayName": user.name,
        "defaultBusinessId": None,
        "preferences": UserPreferences().model_dump(by_alias=True),
        "createdAt": now,
        "updatedAt": now,
    }
    ref.set(data)
    return data


def save_preferences(db: FirestoreClient, uid: str, prefs: UserPreferences) -> None:
    db.collection(col.USERS).document(uid).update(
        {"preferences": prefs.model_dump(by_alias=True), "updatedAt": datetime.now(UTC)}
    )


def list_memberships(db: FirestoreClient, uid: str) -> list[dict[str, Any]]:
    """Memberships of `uid`, each enriched with the business name."""
    snaps = list(
        db.collection(col.BUSINESS_MEMBERS).where(filter=FieldFilter("uid", "==", uid)).stream()
    )
    members = [s.to_dict() or {} for s in snaps]
    if not members:
        return []
    refs = [db.collection(col.BUSINESSES).document(m["businessId"]) for m in members]
    names = {
        b.id: (b.to_dict() or {}).get("businessName", "") for b in db.get_all(refs) if b.exists
    }
    return [
        {"businessId": m["businessId"], "businessName": names[m["businessId"]], "role": m["role"]}
        for m in members
        if m["businessId"] in names
    ]
