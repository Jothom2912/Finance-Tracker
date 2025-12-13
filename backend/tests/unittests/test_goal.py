from pydantic import ValidationError
import pytest
from datetime import date, timedelta
from backend.shared.schemas.goal import GoalBase, GoalCreate 


# Helper data for valid goal creation
VALID_NAME = "Test Goal"
VALID_TARGET = 100.00
VALID_CURRENT = 50.00
REQUIRED_ACCOUNT_ID = 1

# GoalBase Tests

# Target Amount BVA - Negative (INVALID)
def test_base_target_amount_negative_invalid():
    # Arrange
    target_amount = -0.01

    # Act & Assert
    with pytest.raises(ValidationError):
        GoalBase(target_amount=target_amount)


# Target Amount BVA - Zero (VALID)
def test_base_target_amount_zero_valid():
    # Arrange
    target_amount = 0.00
    current_amount = 0.00
    # Act
    goal = GoalBase(target_amount=target_amount, current_amount=current_amount)
    # Assert
    assert goal.target_amount == target_amount

# Current Amount BVA - Negative (INVALID)
def test_base_current_amount_negative_invalid():
    # Arrange
    current_amount = -0.01

    # Act & Assert
    with pytest.raises(ValidationError):
        GoalBase(target_amount=VALID_TARGET, current_amount=current_amount)

# Target Amount Rounding Check
def test_base_target_amount_rounding():
    # Arrange
    input_amount = 100.128
    expected_amount = 100.13

    # Act
    goal = GoalBase(target_amount=input_amount)

    # Assert
    assert goal.target_amount == expected_amount

# Test current amount cant exceed target amount

# Current > Target (INVALID)
def test_base_current_greater_than_target_invalid():
    # Arrange
    target = 100.00
    current = 100.01

    # Act & Assert
    with pytest.raises(ValueError, match="kan ikke være større end target amount"):
        GoalBase(target_amount=target, current_amount=current)

# Current == Target (VALID)
def test_base_current_equal_to_target_valid():
    # Arrange
    target = 100.00
    current = 100.00

    # Act
    goal = GoalBase(target_amount=target, current_amount=current)

    # Assert
    assert goal.target_amount == target
    assert goal.current_amount == current

# Current < Target (VALID)
def test_base_current_less_than_target_valid():
    # Arrange
    target = 100.00
    current = 99.99

    # Act
    goal = GoalBase(target_amount=target, current_amount=current)

    # Assert
    assert goal.target_amount == target
    assert goal.current_amount == current


# Target Date Validation

# Past Date (INVALID)
def test_base_target_date_past_invalid():
    # Arrange
    past_date = date.today() - timedelta(days=1)

    # Act & Assert
    with pytest.raises(ValueError, match="Deadline skal være i fremtiden"):
        GoalBase(target_amount=VALID_TARGET, target_date=past_date)

# Today's Date (INVALID)
def test_base_target_date_today_invalid():
    # Arrange
    today = date.today()

    # Act & Assert
    with pytest.raises(ValueError, match="Deadline skal være i fremtiden"):
        GoalBase(target_amount=VALID_TARGET, target_date=today)


# Future Date (VALID)
def test_base_target_date_future_valid():
    # Arrange
    future_date = date.today() + timedelta(days=1)

    # Act
    goal = GoalBase(target_amount=VALID_TARGET, target_date=future_date)

    # Assert
    assert goal.target_date == future_date

# Name field validation

# Name - Max Length Check (INVALID)
def test_base_name_max_length_invalid():
    # Arrange
    name = "A" * 46

    # Act & Assert
    with pytest.raises(ValidationError):
        GoalBase(target_amount=VALID_TARGET, name=name)

# GoalCreate Tests

# Missing Account ID (INVALID)
def test_create_missing_account_id_invalid():
    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        GoalCreate(target_amount=VALID_TARGET)

    # Assert
    assert "Account_idAccount" in str(excinfo.value)

# Valid Account ID (VALID)
def test_create_account_id_valid():
    # Arrange
    account_id = REQUIRED_ACCOUNT_ID

    # Act
    goal = GoalCreate(target_amount=VALID_TARGET, Account_idAccount=account_id)

    # Assert
    assert goal.Account_idAccount == account_id


# Inheritance Check - Target Date (INVALID)
def test_create_inheritance_target_date_today_invalid():
    # Arrange
    today = date.today()

    # Act & Assert
    with pytest.raises(ValueError, match="Deadline skal være i fremtiden"):
        GoalCreate(
            target_amount=VALID_TARGET,
            Account_idAccount=REQUIRED_ACCOUNT_ID,
            target_date=today
        )
