from datetime import date
from typing import Optional, Any

from fastapi import APIRouter, Query, status

from app.api.v1.deps import Db
from app.core.security import CurrentUser
from app.repositories import businesses as biz_repo
from app.repositories import collections as col
from app.repositories import records as records_repo
from app.repositories import users as users_repo
from app.schemas.business import BusinessOut, BusinessProfileIn
from app.schemas.dashboard import ActionItem, DashboardSummary
from app.services.action_engine import generate_action_plan
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
def get_dashboard(
    access: CanView,
    db: Db,
    customer_name: Optional[str] = Query(None),
    supplier_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
) -> DashboardSummary:
    business = biz_repo.get_business(db, access.business_id)
    
    invoice_filters = {}
    if customer_name:
        invoice_filters["customerName"] = customer_name
    if status:
        invoice_filters["status"] = status
        
    expense_filters = {}
    if supplier_name:
        expense_filters["supplierName"] = supplier_name
    if status:
        expense_filters["status"] = status
        
    invoices = records_repo.list_records(db, col.INVOICES, access, order_by="issueDate", filters=invoice_filters)
    expenses = records_repo.list_records(db, col.EXPENSES, access, order_by="date", filters=expense_filters)
    payments = records_repo.list_records(db, col.PAYMENTS, access, order_by="date")
    documents = records_repo.list_records(db, col.UPLOADED_DOCUMENTS, access, order_by="uploadedAt")
    
    actions = records_repo.list_records(db, col.ACTION_PLANS, access, order_by="createdAt")
    action_items = [ActionItem.model_validate(a) for a in actions if a.get("status") != "dismissed"]

    summary = compute_summary(
        invoices=invoices,
        expenses=expenses,
        payments=payments,
        documents=documents,
        today=date.today(),
        fy_start=business.get("financialYearStart", "april")
    )
    summary.action_plan = action_items
    return summary


@router.post("/{business_id}/actions/generate", response_model=list[ActionItem])
def generate_actions(access: CanAdmin, db: Db) -> list[ActionItem]:
    invoices = records_repo.list_records(db, col.INVOICES, access, order_by="issueDate")
    expenses = records_repo.list_records(db, col.EXPENSES, access, order_by="date")
    
    new_items = generate_action_plan(invoices, expenses, date.today())
    
    # Save the new items to Firestore
    saved_items = []
    for item in new_items:
        data = item.model_dump()
        record_id = data.pop("id", None)
        saved = records_repo.create_record(db, col.ACTION_PLANS, access, data, record_id=record_id)
        saved_items.append(ActionItem.model_validate(saved))
        
    return saved_items


@router.patch("/{business_id}/actions/{action_id}", response_model=ActionItem)
def update_action(action_id: str, payload: dict[str, Any], access: CanAdmin, db: Db) -> ActionItem:
    # Minimal update for status etc
    action_data = records_repo.get_record(db, col.ACTION_PLANS, access, action_id)
    if "status" in payload:
        action_data["status"] = payload["status"]
    
    ref = db.collection(col.ACTION_PLANS).document(action_id)
    ref.update({"status": payload["status"]})
    
    return ActionItem.model_validate({**action_data, "id": action_id})
