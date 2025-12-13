import pytest
from pydantic import ValidationError
from datetime import date
from typing import Optional
from pydantic import BaseModel, ValidationError, Field, field_validator 
from backend.shared.schemas.budget import BudgetCreate, BudgetBase

#BudgetBase tests

# Lower Boundary (N) - VALID (0.00)
def test_base_amount_at_boundary_valid():
    # Arrange
    amount = 0.00

    # Act
    valid_budget = BudgetBase(amount=amount)

    # Assert
    assert valid_budget.amount == amount

# Lower Boundary (N-1) - INVALID (-0.01)
def test_base_amount_below_boundary_invalid():
    # Arrange
    amount = -0.01

    # Act & Assert
    with pytest.raises(ValidationError):
        BudgetBase(amount=amount)

# Rounding Logic Check
def test_base_amount_rounding():
    # Arrange
    input_amount = 99.998
    expected_amount = 100.00

    # Act
    budget = BudgetBase(amount=input_amount)

    # Assert
    assert budget.amount == expected_amount


# Budget Date - Optional Field (Default=None)
def test_base_budget_date_optional_default_none():
    # Act
    budget = BudgetBase(amount=10.00)  # budget_date omitted

    # Assert
    assert budget.budget_date is None


# Budget Date - Valid Date Type
def test_base_budget_date_valid_type():
    # Arrange
    today = date.today()

    # Act
    budget = BudgetBase(amount=10.00, budget_date=today)

    # Assert
    assert budget.budget_date == today


# BudgetCreate tests

# Account ID - Optional Field (Default=None)
def test_create_account_id_optional_default_none():
    # Act
    budget = BudgetCreate(amount=10.00)  # Account_idAccount omitted

    # Assert
    assert budget.Account_idAccount is None


# Account ID - Valid Integer Value
def test_create_account_id_valid_value():
    # Arrange
    valid_id = 5

    # Act
    budget = BudgetCreate(amount=10.00, Account_idAccount=valid_id)

    # Assert
    assert budget.Account_idAccount == valid_id


# Inheritance Check - Amount BVA (Confirming BudgetBase logic is inherited)
def test_create_inheritance_amount_below_boundary_invalid():
    # Arrange
    amount = -0.01

    # Act & Assert
    with pytest.raises(ValidationError):
        BudgetCreate(amount=amount)

# BudgetUpdate Tests

class BudgetUpdate(BaseModel):
    # For updates, all fields are optional
    amount: Optional[float] = None
    budget_date: Optional[date] = None
    Account_idAccount: Optional[int] = None


# Update Schema - All Fields Omitted - VALID
def test_update_all_fields_omitted_valid():
    # Act
    update_data = BudgetUpdate()

    # Assert
    assert update_data.amount is None
    assert update_data.budget_date is None
    assert update_data.Account_idAccount is None


# Update Schema - Partial Update (Only amount provided) - VALID
def test_update_partial_update_valid():
    # Arrange
    input_amount = 500.55

    # Act
    update_data = BudgetUpdate(amount=input_amount)

    # Assert
    assert update_data.amount == input_amount
    assert update_data.budget_date is None
    assert update_data.Account_idAccount is None