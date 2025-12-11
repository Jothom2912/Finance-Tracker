from pydantic import ValidationError
import pytest
from datetime import date, timedelta
from backend.shared.schemas.transaction import TransactionBase, TransactionType # Assuming these imports

# 1. Zero Amount (UGYLDIG)
def test_base_amount_is_zero_invalid():
    # ACT & ASSERT
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionBase(amount=0.00, type=TransactionType.income)

# 2. Near-Zero Amount (Floating Point Handling) (UGYLDIG)
def test_base_amount_near_zero_invalid():
    # ACT & ASSERT (Tests the abs(v) < 0.001 check)
    with pytest.raises(ValueError, match="Transaction amount cannot be zero"):
        TransactionBase(amount=0.000001, type=TransactionType.expense)

# 3. Lower Boundary (N-1): -0.01 (Gyldig, expense)
def test_base_amount_negative_boundary_valid():
    amount = -0.01
    valid_txn = TransactionBase(amount=amount, type=TransactionType.expense)
    assert valid_txn.amount == amount

# 4. Upper Boundary (N+1): 0.01 (Gyldig, income)
def test_base_amount_positive_boundary_valid():
    amount = 0.01
    valid_txn = TransactionBase(amount=amount, type=TransactionType.income)
    assert valid_txn.amount == amount

# 5. Amount Rounding Check
def test_base_amount_rounding():
    input_amount = 45.678
    expected_amount = 45.68
    txn = TransactionBase(amount=input_amount, type=TransactionType.income)
    assert txn.amount == expected_amount

