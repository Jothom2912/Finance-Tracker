import pytest
from pydantic import ValidationError
from datetime import date, timedelta
from backend.shared.schemas.transaction import (
    TransactionBase,
    TransactionType,
    TransactionCreate,
)


# TransactionBase — Amount BVA

# Zero Amount (INVALID)
def test_base_amount_is_zero_invalid():
    # Arrange
    amount = 0.00

    # Act & Assert
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionBase(amount=amount, type=TransactionType.income)


# Near-Zero Amount (Floating Point Handling) (INVALID)
def test_base_amount_near_zero_invalid():
    # Arrange
    amount = 0.000001

    # Act & Assert
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionBase(amount=amount, type=TransactionType.expense)


# Lower Boundary (N-1): -0.01 (VALID, expense)
def test_base_amount_negative_boundary_valid():
    # Arrange
    amount = -0.01

    # Act
    txn = TransactionBase(amount=amount, type=TransactionType.expense)

    # Assert
    assert txn.amount == amount


# Upper Boundary (N+1): 0.01 (VALID, income)
def test_base_amount_positive_boundary_valid():
    # Arrange
    amount = 0.01

    # Act
    txn = TransactionBase(amount=amount, type=TransactionType.income)

    # Assert
    assert txn.amount == amount


# Amount Rounding Check
def test_base_amount_rounding():
    # Arrange
    input_amount = 45.678
    expected_amount = 45.68

    # Act
    txn = TransactionBase(amount=input_amount, type=TransactionType.income)

    # Assert
    assert txn.amount == expected_amount


# TransactionBase — Type Validation

# Valid Type: income
def test_base_type_valid_income():
    # Act
    txn = TransactionBase(amount=10.00, type=TransactionType.income)

    # Assert
    assert txn.type == TransactionType.income


# Valid Type: expense
def test_base_type_valid_expense():
    # Act
    txn = TransactionBase(amount=-10.00, type=TransactionType.expense)

    # Assert
    assert txn.type == TransactionType.expense


# Invalid Type (Not an Enum member)
def test_base_type_invalid_value():
    # Arrange
    invalid_type = "transfer"

    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        TransactionBase(amount=10.00, type=invalid_type)

    # Assert
    assert "type" in str(excinfo.value)
    assert "Input should be 'income' or 'expense'" in str(excinfo.value)


# TransactionBase — Date Validation

# Date: Today (VALID)
def test_base_date_today_valid():
    # Arrange
    today = date.today()

    # Act
    txn = TransactionBase(
        amount=10.00,
        type=TransactionType.income,
        date=today,
    )

    # Assert
    assert txn.date == today


# Date: Past Date (VALID)
def test_base_date_past_valid():
    # Arrange
    past_date = date.today() - timedelta(days=1)

    # Act
    txn = TransactionBase(
        amount=10.00,
        type=TransactionType.income,
        date=past_date,
    )

    # Assert
    assert txn.date == past_date


# Date: Future Date (INVALID)
def test_base_date_future_invalid():
    # Arrange
    future_date = date.today() + timedelta(days=1)

    # Act & Assert
    with pytest.raises(ValueError, match="Transaction date cannot be in the future"):
        TransactionBase(
            amount=10.00,
            type=TransactionType.income,
            date=future_date,
        )


# TransactionBase — Description Validation

# Description Max Length (INVALID)
def test_base_description_max_length_invalid():
    # Arrange
    description = "A" * 256

    # Act & Assert
    with pytest.raises(ValidationError):
        TransactionBase(
            amount=10.00,
            type=TransactionType.income,
            description=description,
        )


# TransactionCreate Tests

REQUIRED_CAT_ID = 1


# Missing Category ID (INVALID)
def test_create_missing_category_id_invalid():
    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        TransactionCreate(amount=10.00, type=TransactionType.income)

    # Assert
    assert (
        "Category_idCategory" in str(excinfo.value)
        or "category_id" in str(excinfo.value)
    )


# Valid Category ID (VALID)
def test_create_category_id_valid():
    # Arrange
    category_id = REQUIRED_CAT_ID

    # Act
    txn = TransactionCreate(
        amount=10.00,
        type=TransactionType.income,
        category_id=category_id,  # alias name
    )

    # Assert
    assert txn.Category_idCategory == category_id


# Inheritance Check — Zero Amount (INVALID)
def test_create_inheritance_amount_is_zero_invalid():
    # Arrange
    amount = 0.00

    # Act & Assert
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionCreate(
            amount=amount,
            type=TransactionType.expense,
            Category_idCategory=REQUIRED_CAT_ID,
        )
