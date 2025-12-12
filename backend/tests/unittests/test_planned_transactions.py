from pydantic import ValidationError
import pytest
from datetime import date, timedelta
from typing import Optional
# Assuming you will import your schemas from your main file
from backend.shared.schemas.planned_transactions import PlannedTransactionsBase, PlannedTransactionsCreate 
from backend.shared.schemas.transaction import TransactionBase 
from backend.shared.schemas.planned_transactions import TransactionBase 


# MOCK DEPENDENCY 
# This class acts as a mock for the imported PLANNED_TRANSACTION_BVA
# to satisfy the schema's requirement for valid_intervals.
class PLANNED_TRANSACTION_BVA:
    valid_intervals = ["daily", "weekly", "monthly"]

# --- HELPER CONSTANTS ---
VALID_AMOUNT = 100.00



# Unit Logic Tests (Using PlannedTransactionsBase)
# Amount Boundary Value Analysis

# Zero Amount (invalid)
def test_base_amount_is_zero_invalid():
    with pytest.raises(ValueError, match="Amount må IKKE være 0"):
        PlannedTransactionsBase(amount=0.00)

#Near-Zero Amount (Floating Point Handling) (valid)
def test_base_amount_near_zero_invalid():
    with pytest.raises(ValueError, match="Amount må IKKE være 0"):
        PlannedTransactionsBase(amount=0.0000001)

#Lower Boundary: -0.01 (valid)
def test_base_amount_negative_boundary_valid():
    amount = -0.01
    valid_txn = PlannedTransactionsBase(amount=amount)
    assert valid_txn.amount == amount

# Amount Rounding Check
def test_base_amount_rounding():
    input_amount = 123.456
    expected_amount = 123.46
    txn = PlannedTransactionsBase(amount=input_amount)
    assert txn.amount == expected_amount


#Planned Date Validation Future or Current Date

#Date - Past Date (invalid)
def test_base_planned_date_past_invalid():
    past_date = date.today() - timedelta(days=1)
    with pytest.raises(ValueError, match="Planned date må ikke være i fortiden"):
        PlannedTransactionsBase(amount=VALID_AMOUNT, planned_date=past_date)

# Date - Today's Date (valid)
def test_base_planned_date_today_valid():
    today = date.today()
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, planned_date=today)
    assert txn.planned_date == today

# Date - Future Date (valid)
def test_base_planned_date_future_valid():
    future_date = date.today() + timedelta(days=1)
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, planned_date=future_date)
    assert txn.planned_date == future_date


# Repeat Interval Validation 

# Interval - Valid Value 'weekly'
def test_base_repeat_interval_weekly_valid():
    interval = "weekly"
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, repeat_interval=interval)
    assert txn.repeat_interval == interval

# Interval - Invalid Value (Uses the mocked list)
def test_base_repeat_interval_invalid_value():
    invalid_interval = "yearly"
    with pytest.raises(ValueError, match="Repeat interval må være en af"):
        PlannedTransactionsBase(amount=VALID_AMOUNT, repeat_interval=invalid_interval)

# Interval - Valid Value None (Optional field)
def test_base_repeat_interval_none_valid():
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, repeat_interval=None)
    assert txn.repeat_interval is None


#Name Field Validation 

#Name - Max Length Check (Max length is 45)
def test_base_name_max_length_invalid():
    with pytest.raises(ValidationError):
        PlannedTransactionsBase(amount=VALID_AMOUNT, name="A" * 46)



# Derived Integration Tests (Using PlannedTransactionsCreate)

#Basic Instantiation Check (VALID)
def test_create_schema_basic_instantiation_valid():
    # Confirms that the derived schema is correctly constructed
    txn = PlannedTransactionsCreate(amount=VALID_AMOUNT, name="Rent")
    assert txn.name == "Rent"

#Inheritance Check - Past Date (Confirming Base logic is inherited)
def test_create_inheritance_past_date_invalid():
    past_date = date.today() - timedelta(days=1)
    with pytest.raises(ValueError, match="Planned date må ikke være i fortiden"):
        PlannedTransactionsCreate(amount=VALID_AMOUNT, planned_date=past_date)