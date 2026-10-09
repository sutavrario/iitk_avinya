from fastapi import APIRouter

from app.api.v1.deps import Db
from app.core.security import CurrentUser
from app.repositories import users as users_repo
from app.schemas.user import MembershipOut, MeResponse, UserOut, UserPreferences

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=MeResponse)
def get_me(user: CurrentUser, db: Db) -> MeResponse:
    """Current user's profile and accessible businesses. Creates the profile on first call."""
    data = users_repo.ensure_user(db, user)
    memberships = [
        MembershipOut.model_validate(m) for m in users_repo.list_memberships(db, user.uid)
    ]
    accessible = {m.business_id for m in memberships}
    default = data.get("defaultBusinessId")
    return MeResponse(
        user=UserOut(
            uid=user.uid,
            email=user.email,
            display_name=data.get("displayName") or user.name,
            email_verified=user.email_verified,
            # Never point the client at a business it no longer has access to.
            default_business_id=default
            if default in accessible
            else (memberships[0].business_id if memberships else None),
            preferences=UserPreferences.model_validate(data.get("preferences") or {}),
        ),
        memberships=memberships,
    )


@router.get("/preferences", response_model=UserPreferences)
def get_preferences(user: CurrentUser, db: Db) -> UserPreferences:
    return UserPreferences.model_validate(users_repo.ensure_user(db, user).get("preferences") or {})


@router.put("/preferences", response_model=UserPreferences)
def put_preferences(prefs: UserPreferences, user: CurrentUser, db: Db) -> UserPreferences:
    users_repo.ensure_user(db, user)
    users_repo.save_preferences(db, user.uid, prefs)
    return prefs
