from datetime import UTC, datetime
from typing import Any

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1 import FieldFilter

from app.core.errors import ConflictError, NotFoundError
from app.core.security import AuthenticatedUser
from app.repositories import collections as col
from app.schemas.business import BusinessProfileIn
from app.services.authorization import Role, membership_id


def _profile_data(profile: BusinessProfileIn) -> dict[str, Any]:
    return profile.model_dump(by_alias=True, exclude_none=False)


def create_business(
    db: FirestoreClient, user: AuthenticatedUser, profile: BusinessProfileIn
) -> dict[str, Any]:
    """Create a business, make the caller its owner, and set it as their default — atomically."""
    owned = (
        db.collection(col.BUSINESS_MEMBERS)
        .where(filter=FieldFilter("uid", "==", user.uid))
        .where(filter=FieldFilter("role", "==", Role.OWNER.value))
        .limit(1)
        .get()
    )
    if owned:
        raise ConflictError(
            "You already have a business. Edit it from Settings instead.", code="business_exists"
        )

    now = datetime.now(UTC)
    biz_ref = db.collection(col.BUSINESSES).document()
    data = {
        **_profile_data(profile),
        "ownerUid": user.uid,
        "createdBy": user.uid,
        "createdAt": now,
        "updatedAt": now,
    }

    batch = db.batch()
    batch.set(biz_ref, data)
    batch.set(
        db.collection(col.BUSINESS_MEMBERS).document(membership_id(biz_ref.id, user.uid)),
        {"businessId": biz_ref.id, "uid": user.uid, "role": Role.OWNER.value, "createdAt": now},
    )
    batch.set(
        db.collection(col.USERS).document(user.uid),
        {
            "defaultBusinessId": biz_ref.id,
            # Start the copilot/app in the language chosen during onboarding.
            "preferences": {
                "copilotLanguage": profile.preferred_language,
                "interfaceLanguage": profile.preferred_language,
            },
            "updatedAt": now,
        },
        merge=True,
    )
    batch.commit()
    return {**data, "id": biz_ref.id}


def get_business(db: FirestoreClient, business_id: str) -> dict[str, Any]:
    snap = db.collection(col.BUSINESSES).document(business_id).get()
    if not snap.exists:
        raise NotFoundError("Business not found.", code="business_not_found")
    return {**(snap.to_dict() or {}), "id": snap.id}


def update_business(
    db: FirestoreClient, business_id: str, profile: BusinessProfileIn, uid: str
) -> dict[str, Any]:
    ref = db.collection(col.BUSINESSES).document(business_id)
    ref.update({**_profile_data(profile), "updatedAt": datetime.now(UTC), "updatedBy": uid})
    return get_business(db, business_id)
