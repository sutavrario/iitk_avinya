from datetime import date

from fastapi import APIRouter, status

from app.api.v1.deps import Db
from app.core.security import CurrentUser
from app.repositories import businesses as biz_repo
from app.repositories import collections as col
from app.repositories import records as records_repo
from app.repositories import users as users_repo
from app.schemas.business import BusinessOut, BusinessProfileIn
from app.schemas.dashboard import DashboardSummary
from app.services.authorization import CanAdmin, CanView, Role
from app.services.dashboard import compute_summary

router = APIRouter(prefix="/businesses", tags=["businesses"])


@router.post("", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
def create_business(profile: BusinessProfileIn, user: CurrentUser, db: Db) -> BusinessOut:
    """Onboarding: create the caller's business. The caller becomes its owner."""
    users_repo.ensure_user(db, user)
    data = biz_repo.create_business(db, user, profile)
    return BusinessOut.model_validate({**data, "role": Role.OWNER.value})


@router.get("/{business_id}", response_model=BusinessOut)
def get_business(access: CanView, db: Db) -> BusinessOut:
    data = biz_repo.get_business(db, access.business_id)
    return BusinessOut.model_validate({**data, "role": access.role.value})


@router.put("/{business_id}", response_model=BusinessOut)
def update_business(profile: BusinessProfileIn, access: CanAdmin, db: Db) -> BusinessOut:
    data = biz_repo.update_business(db, access.business_id, profile, access.user.uid)
    return BusinessOut.model_validate({**data, "role": access.role.value})


@router.get("/{business_id}/dashboard", response_model=DashboardSummary)
def get_dashboard(access: CanView, db: Db) -> DashboardSummary:
    business = biz_repo.get_business(db, access.business_id)
    invoices = records_repo.list_records(db, col.INVOICES, access, order_by="issueDate")
    payments = records_repo.list_records(db, col.PAYMENTS, access, order_by="date")
    return compute_summary(
        invoices, payments, today=date.today(), fy_start=business.get("financialYearStart", "april")
    )
