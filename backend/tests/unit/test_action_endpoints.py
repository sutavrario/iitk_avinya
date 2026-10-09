from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.businesses import get_dashboard, update_action, generate_actions
from app.services.authorization import BusinessAccess, Role
from app.core.errors import NotFoundError
from app.repositories import collections as col

def test_get_dashboard_access_control():
    mock_db = MagicMock()
    mock_user = MagicMock()
    mock_user.uid = "user1"
    
    # Simulate a CanView dependency resolving successfully for business_id "biz1"
    mock_access = BusinessAccess(business_id="biz1", user=mock_user, role=Role.VIEWER)

    with patch("app.api.v1.businesses.biz_repo") as mock_biz_repo, \
         patch("app.api.v1.businesses.records_repo") as mock_records_repo:
        
        mock_biz_repo.get_business.return_value = {"id": "biz1"}
        mock_records_repo.list_records.return_value = []
        
        get_dashboard(mock_access, mock_db)
        
        # Verify list_records was called with the correct BusinessAccess (which contains biz1)
        # for ACTION_PLANS.
        calls = mock_records_repo.list_records.call_args_list
        action_plan_calls = [c for c in calls if c.args[1] == col.ACTION_PLANS]
        assert len(action_plan_calls) == 1
        
        # The third argument is the access object
        called_access = action_plan_calls[0].args[2]
        assert called_access.business_id == "biz1"


def test_update_action_access_control_other_business():
    mock_db = MagicMock()
    mock_user = MagicMock()
    mock_user.uid = "user1"
    
    # Caller has access to biz1
    mock_access = BusinessAccess(business_id="biz1", user=mock_user, role=Role.ADMIN)

    with patch("app.api.v1.businesses.records_repo") as mock_records_repo:
        # If records_repo.get_record raises NotFoundError (which it does if the record belongs to another business)
        mock_records_repo.get_record.side_effect = NotFoundError("Record not found.")
        
        with pytest.raises(NotFoundError):
            update_action("action_biz2_123", {"status": "completed"}, mock_access, mock_db)
            
        mock_records_repo.get_record.assert_called_once_with(
            mock_db, col.ACTION_PLANS, mock_access, "action_biz2_123"
        )
