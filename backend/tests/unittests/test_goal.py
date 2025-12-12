from pydantic import ValidationError
import pytest
from datetime import date, timedelta
from backend.shared.schemas.goal import GoalBase, GoalCreate 


# Helper data for valid goal creation
VALID_NAME = "Test Goal"
VALID_TARGET = 100.00
VALID_CURRENT = 50.00

# Target Amount BVA - Negative (UGYLDIG)
def test_base_target_amount_negative_invalid():
    # ACT & ASSERT (Test the ge=0 constraint and custom validator)
    with pytest.raises(ValidationError):
        GoalBase(target_amount=-0.01)

# Target Amount BVA - Zero (GYLDIG)
def test_base_target_amount_zero_valid():
    goal = GoalBase(target_amount=0.00, current_amount=0.00)
    assert goal.target_amount == 0.00

# 3. Current Amount BVA - Negative (UGYLDIG)
def test_base_current_amount_negative_invalid():
    # ACT & ASSERT
    with pytest.raises(ValidationError):
        GoalBase(target_amount=VALID_TARGET, current_amount=-0.01)

# Target Amount Rounding Check
def test_base_target_amount_rounding():
    input_amount = 100.128
    expected_amount = 100.13
    goal = GoalBase(target_amount=input_amount)
    assert goal.target_amount == expected_amount

# Test current amount cant exceed target amount

# Current > Target (Invalid)
def test_base_current_greater_than_target_invalid():
    target = 100.00
    current = 100.01
    # ACT & ASSERT (Expect ValueError from the custom validator)
    with pytest.raises(ValueError, match="kan ikke være større end target amount"):
        GoalBase(target_amount=target, current_amount=current)

# Current == Target (Valid)
def test_base_current_equal_to_target_valid():
    target = 100.00
    current = 100.00
    goal = GoalBase(target_amount=target, current_amount=current)
    assert goal.target_amount == target and goal.current_amount == current

# Current < Target (Valid)
def test_base_current_less_than_target_valid():
    target = 100.00
    current = 99.99
    goal = GoalBase(target_amount=target, current_amount=current)
    assert goal.target_amount == target and goal.current_amount == current


# Target Date in the future 

# Target Date - Past Date (Invalid)
def test_base_target_date_past_invalid():
    past_date = date.today() - timedelta(days=1)
    # ACT & ASSERT (Expect ValueError from the custom validator)
    with pytest.raises(ValueError, match="Deadline skal være i fremtiden"):
        GoalBase(target_amount=VALID_TARGET, target_date=past_date)

# Target Date - Today's Date (Valid)
def test_base_target_date_today_invalid():
    today = date.today()
    # ACT & ASSERT
    with pytest.raises(ValueError, match="Deadline skal være i fremtiden"):
        GoalBase(target_amount=VALID_TARGET, target_date=today)

# Target Date - Future Date (Valid)
def test_base_target_date_future_valid():
    future_date = date.today() + timedelta(days=1)
    goal = GoalBase(target_amount=VALID_TARGET, target_date=future_date)
    assert goal.target_date == future_date

# Name field validation

# Name - Max Length Check (Max length is 45)
def test_base_name_max_length_invalid():
    # ACT & ASSERT
    with pytest.raises(ValidationError):
        GoalBase(target_amount=VALID_TARGET, name="A" * 46)

#Test with  AccountId

REQUIRED_ACCOUNT_ID = 1

# Required Field - Missing Account ID - INVALID
def test_create_missing_account_id_invalid():
    # ACT & ASSERT (Account_idAccount is required)
    with pytest.raises(ValidationError) as excinfo:
        GoalCreate(target_amount=VALID_TARGET)
    
    assert "Account_idAccount" in str(excinfo.value)

# Required Field - Valid Account ID - VALID
def test_create_account_id_valid():
    goal = GoalCreate(target_amount=VALID_TARGET, Account_idAccount=REQUIRED_ACCOUNT_ID)
    assert goal.Account_idAccount == REQUIRED_ACCOUNT_ID

# Inheritance Check - Target Date (Confirming GoalBase logic is inherited)
def test_create_inheritance_target_date_today_invalid():
    today = date.today()
    # ACT & ASSERT (This confirms the validate_target_date logic is active in GoalCreate)
    with pytest.raises(ValueError, match="Deadline skal være i fremtiden"):
        GoalCreate(target_amount=VALID_TARGET, Account_idAccount=REQUIRED_ACCOUNT_ID, target_date=today)