from pydantic import ValidationError
import pytest
from datetime import date, timedelta
from backend.shared.schemas.transaction import TransactionBase, TransactionType, TransactionCreate 

#BVA

# Zero Amount (UGYLDIG)
def test_base_amount_is_zero_invalid():
    # ACT & ASSERT
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionBase(amount=0.00, type=TransactionType.income)

# Near-Zero Amount (Floating Point Handling) (UGYLDIG)
def test_base_amount_near_zero_invalid():
    # ACT & ASSERT (Tests the abs(v) < 0.001 check)
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionBase(amount=0.000001, type=TransactionType.expense)

# Lower Boundary (N-1): -0.01 (Gyldig, expense)
def test_base_amount_negative_boundary_valid():
    amount = -0.01
    valid_txn = TransactionBase(amount=amount, type=TransactionType.expense)
    assert valid_txn.amount == amount

# Upper Boundary (N+1): 0.01 (Gyldig, income)
def test_base_amount_positive_boundary_valid():
    amount = 0.01
    valid_txn = TransactionBase(amount=amount, type=TransactionType.income)
    assert valid_txn.amount == amount

# Amount Rounding Check
def test_base_amount_rounding():
    input_amount = 45.678
    expected_amount = 45.68
    txn = TransactionBase(amount=input_amount, type=TransactionType.income)
    assert txn.amount == expected_amount


# Type Validation Check

# Type - Valid Value 'income'
def test_base_type_valid_income():
    txn = TransactionBase(amount=10.00, type=TransactionType.income)
    assert txn.type == TransactionType.income

# Type - Valid Value 'expense'
def test_base_type_valid_expense():
    txn = TransactionBase(amount=-10.00, type=TransactionType.expense)
    assert txn.type == TransactionType.expense

# Type - Invalid Value (Not an Enum member)
def test_base_type_invalid_value():
    # ACT & ASSERT (Pydantic handles enum failures with a ValidationError)
    with pytest.raises(ValidationError) as excinfo:
        # Pass a string not in the enum
        TransactionBase(amount=10.00, type="transfer")
    
    # Assert that the error is for the 'type' field
    assert 'type' in str(excinfo.value)
    
    # NEW ASSERTION: Check for the exact message showing the allowed enum values
    # The error message is: "Input should be 'income' or 'expense'"
    assert "Input should be 'income' or 'expense'" in str(excinfo.value)


# Date Validation Check

# Date - Valid Date (Today)
def test_base_date_today_valid():
    today = date.today()
    txn = TransactionBase(amount=10.00, type=TransactionType.income, transaction_date=today)
    assert txn.transaction_date == today

# Date - Valid Date (In the past)
def test_base_date_past_valid():
    past_date = date.today() - timedelta(days=1)
    txn = TransactionBase(amount=10.00, type=TransactionType.income, transaction_date=past_date)
    assert txn.transaction_date == past_date

# Date - Future Date (UGYLDIG)
def test_base_date_future_invalid():
    future_date = date.today() + timedelta(days=1)
    # ACT & ASSERT (Expect ValueError from the custom validator)
    with pytest.raises(ValueError, match="Transaction date cannot be in the future"):
        TransactionBase(amount=10.00, type=TransactionType.income, transaction_date=future_date)

# Decscription Validation Check

# Description - Max Length Check
def test_base_description_max_length_invalid():
    # ACT & ASSERT (Max length is 255)
    with pytest.raises(ValidationError):
        TransactionBase(amount=10.00, type=TransactionType.income, description="A" * 256)



# TransactionCreate Tests

REQUIRED_CAT_ID = 1

# 13. Required Field - Missing Category ID - INVALID
def test_create_missing_category_id_invalid():
    # ACT & ASSERT (Category_idCategory is required)
    with pytest.raises(ValidationError) as excinfo:
        TransactionCreate(amount=10.00, type=TransactionType.income)
    
    # Alias is 'category_id', but error usually references the underlying field name
    assert "Category_idCategory" in str(excinfo.value) or "category_id" in str(excinfo.value)

# Required Field - Valid Category ID - VALID
def test_create_category_id_valid():
    REQUIRED_CAT_ID = 1
    
    # ACT: Must use the alias name 'category_id' for input
    txn = TransactionCreate(
        amount=10.00, 
        type=TransactionType.income, 
        category_id=REQUIRED_CAT_ID  # <--- FIXED: Using alias name
    )
    
    # ASSERT: Assert the final attribute name
    assert txn.Category_idCategory == REQUIRED_CAT_ID

# 15. Inheritance Check - Zero Amount (Confirming TransactionBase logic is inherited)
def test_create_inheritance_amount_is_zero_invalid():
    # ACT & ASSERT (This confirms that the validate_amount_not_zero logic is active in TransactionCreate)
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionCreate(amount=0.00, type=TransactionType.expense, Category_idCategory=REQUIRED_CAT_ID)