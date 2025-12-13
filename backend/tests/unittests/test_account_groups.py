from pydantic import ValidationError
import pytest
from typing import List
from backend.shared.schemas.account_groups import AccountGroupsBase, AccountGroupsCreate

# MOCK DEPENDENCY
# This class acts as a mock for the imported ACCOUNT_GROUP_BVA
class ACCOUNT_GROUP_BVA:
    name_min_length = 1
    name_max_length = 30
    max_users = 20

# --- HELPER CONSTANTS ---
VALID_NAME = "Family Budget"
VALID_MAX_USERS = 5

# Unit logic tests for AccountGroupsBase schema

#Name Length and Content BVA

#Min Length (N-1) - INVALID (0 chars)
def test_base_name_min_length_below_boundary_invalid():
    with pytest.raises(ValidationError):
        AccountGroupsBase(name="", max_users=VALID_MAX_USERS)



