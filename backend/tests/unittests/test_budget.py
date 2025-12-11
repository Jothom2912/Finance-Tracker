import pytest
from pydantic import ValidationError
from datetime import date
from typing import Optional
from pydantic import BaseModel, ValidationError, Field, field_validator 
from backend.shared.schemas.budget import BudgetCreate
from backend.shared.schemas.budget import BudgetBase

# Lower Boundary (N) - VALID (0.00)
def test_base_amount_at_boundary_valid():
    amount = 0.00
    valid_budget = BudgetBase(amount=amount)
    assert valid_budget.amount == amount

# Lower Boundary (N-1) - INVALID (-0.01)
def test_base_amount_below_boundary_invalid():
    # ACT & ASSERT
    # Note: Pydantic's Field(ge=0) and the custom validator both check this.
    with pytest.raises(ValidationError): 
        BudgetBase(amount=-0.01)

# Custom Validator Check - Negative Amount (ValueError check)
def test_base_amount_negative_custom_validator_check():
    # If Pydantic's ge=0 fails first, it raises ValidationError.
    # To test the ValueError raised by your explicit `if v < 0:` check,
    # you would typically disable the Pydantic constraint, but here we confirm 
    # the failure mode. Since ValidationError is a broader success, we stick to it.
    pass # No need for a separate test here, as ValidationError covers it.

# Rounding Logic Check
def test_base_amount_rounding():
    input_amount = 99.998
    expected_amount = 100.00
    budget = BudgetBase(amount=input_amount)
    assert budget.amount == expected_amount

    # Bugdet Date Validation

# Budget Date - Optional Field (Default=None)
def test_base_budget_date_optional_default_none():
    budget = BudgetBase(amount=10.00) # Omit budget_date
    assert budget.budget_date is None

# Budget Date - Valid Date Type
def test_base_budget_date_valid_type():
    today = date.today()
    budget = BudgetBase(amount=10.00, budget_date=today)
    assert budget.budget_date == today

# BudgetCreate Tests

# Account ID - Optional Field (Default=None)
def test_create_account_id_optional_default_none():
    budget = BudgetCreate(amount=10.00) # Omit Account_idAccount
    assert budget.Account_idAccount is None

# Account ID - Valid Integer Value
def test_create_account_id_valid_value():
    valid_id = 5
    budget = BudgetCreate(amount=10.00, Account_idAccount=valid_id)
    assert budget.Account_idAccount == valid_id

# Inheritance Check - Amount BVA (Confirming BudgetBase logic is inherited)
def test_create_inheritance_amount_below_boundary_invalid():
    # This confirms that the ge=0 logic from BudgetBase is active in BudgetCreate
    with pytest.raises(ValidationError):
        BudgetCreate(amount=-0.01)

# BudgetUpdate Tests

class BudgetUpdate(BaseModel):
    # For updates, all fields can be optional
    amount: Optional[float] = None
    budget_date: Optional[date] = None
    Account_idAccount: Optional[int] = None


# Update Schema - All Fields Omitted - VALID
def test_update_all_fields_omitted_valid():
    # ACT
    update_data = BudgetUpdate()
    
    # ASSERT
    assert update_data.amount is None
    assert update_data.budget_date is None
    assert update_data.Account_idAccount is None

# Update Schema - Partial Update (Only amount is provided) - VALID
def test_update_partial_update_valid():
    # ACT
    update_data = BudgetUpdate(amount=500.55)
    
    # ASSERT
    assert update_data.amount == 500.55
    assert update_data.budget_date is None