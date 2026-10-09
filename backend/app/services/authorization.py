"""Business-level authorization.

The server never trusts a businessId from the client: every business-scoped route takes the
business ID from the URL and checks for a membership document
`businessMembers/{businessId}_{uid}` before doing anything else.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, Path
from google.cloud.firestore import Client as FirestoreClient

from app.core.errors import ForbiddenError, NotFoundError
from app.core.firebase import get_db
from app.core.security import AuthenticatedUser, get_current_user
from app.repositories import collections as col


class Role(StrEnum):
    VIEWER = "viewer"
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"


_RANK: dict[Role, int] = {Role.VIEWER: 0, Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}


def role_allows(actual: Role, required: Role) -> bool:
    return _RANK[actual] >= _RANK[required]


@dataclass(frozen=True)
class BusinessAccess:
    """Proof that `user` may act on `business_id` with `role`. Only created by `require_role`."""

    business_id: str
    user: AuthenticatedUser
    role: Role


def membership_id(business_id: str, uid: str) -> str:
    return f"{business_id}_{uid}"


# Firestore document IDs we generate are 20 alphanumerics; reject anything odd early.
BusinessIdPath = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{1,64}$", description="Business ID")]


def require_role(required: Role):  # type: ignore[no-untyped-def]
    """Dependency factory: caller must be a member of the URL's business with `required` role."""

    def dependency(
        business_id: BusinessIdPath,
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        db: Annotated[FirestoreClient, Depends(get_db)],
    ) -> BusinessAccess:
        snap = (
            db.collection(col.BUSINESS_MEMBERS).document(membership_id(business_id, user.uid)).get()
        )
        data = snap.to_dict() if snap.exists else None
        # Same response for "doesn't exist" and "not a member" so IDs can't be probed.
        if not data or data.get("uid") != user.uid or data.get("businessId") != business_id:
            raise NotFoundError("Business not found.", code="business_not_found")
        try:
            role = Role(str(data.get("role")))
        except ValueError as exc:
            raise ForbiddenError("Your access to this business is not configured.") from exc
        if not role_allows(role, required):
            raise ForbiddenError(
                f"Your role ({role.value}) can't do this. Ask the business owner for access.",
                code="insufficient_role",
            )
        return BusinessAccess(business_id=business_id, user=user, role=role)

    return dependency


CanView = Annotated[BusinessAccess, Depends(require_role(Role.VIEWER))]
CanEdit = Annotated[BusinessAccess, Depends(require_role(Role.MEMBER))]
CanAdmin = Annotated[BusinessAccess, Depends(require_role(Role.ADMIN))]
