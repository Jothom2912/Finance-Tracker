# backend/tests/test_bva_validation.py
"""
Boundary Value Analysis (BVA) Tests for all models.

Disse tests validerer grænseværdier for alle entities. BVA-tests fokuserer på værdier
lige ved grænsen af gyldige/ugyldige partitioner for at identificere fejl.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from pydantic import ValidationError

# ============================================================================
# CATEGORY BVA TESTS (4.1)
# ============================================================================

#done
def test_category_name_boundary_values():
    """BVA: Name længde grænseværdier: 0, 1, 30, 31"""
    from backend.shared.schemas.category import CategoryCreate
    
    # 0 chars - INVALID
    with pytest.raises(ValidationError):
        CategoryCreate(name="", type="income")
    
    # 1 char - VALID (grænse)
    valid = CategoryCreate(name="A", type="income")
    assert valid.name == "A"
    
    # 30 chars - VALID (grænse)
    valid = CategoryCreate(name="A" * 30, type="income")
    assert len(valid.name) == 30
    
    # 31 chars - INVALID
    with pytest.raises(ValidationError):
        CategoryCreate(name="A" * 31, type="income")


def test_category_type_boundary_values():
    """BVA: Type må være 'income' eller 'expense'"""
    from backend.shared.schemas.category import CategoryCreate
    
    # Valid types
    valid1 = CategoryCreate(name="Test", type="income")
    assert valid1.type == "income"
    
    valid2 = CategoryCreate(name="Test", type="expense")
    assert valid2.type == "expense"
    
    # Invalid types
    with pytest.raises(ValidationError):
        CategoryCreate(name="Test", type="saving")
    
    with pytest.raises(ValidationError):
        CategoryCreate(name="Test", type="")
    
    with pytest.raises(ValidationError):
        CategoryCreate(name="Test", type="INCOME")  # Case-sensitive


def test_category_description_boundary_values():
    """BVA: Description max 200 chars"""
    from backend.shared.schemas.category import CategoryCreate
    
    # 200 chars - VALID (grænse)
    valid = CategoryCreate(name="Test", type="income", description="A" * 200)
    assert len(valid.description) == 200
    
    # 201 chars - INVALID
    with pytest.raises(ValidationError):
        CategoryCreate(name="Test", type="income", description="A" * 201)
    
    # None/empty - VALID (optional field)
    valid = CategoryCreate(name="Test", type="income", description=None)
    assert valid.description is None


# ============================================================================
# BUDGET BVA TESTS (4.2)
# ============================================================================

def test_budget_amount_boundary_values():
    """BVA: Amount grænseværdier: -0.01 (invalid), 0 (valid), 0.01 (valid)"""
    from backend.shared.schemas.budget import BudgetCreate
    
    # -0.01 - INVALID
    with pytest.raises(ValidationError):
        BudgetCreate(
            category_id=1,
            amount=-0.01,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1)
        )
    
    # 0 - VALID (grænse)
    valid = BudgetCreate(
        category_id=1,
        amount=0.00,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1)
    )
    assert abs(valid.amount - 0.00) < 0.001
    
    # 0.01 - VALID
    valid = BudgetCreate(
        category_id=1,
        amount=0.01,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=1)
    )
    assert abs(valid.amount - 0.01) < 0.001


def test_budget_period_boundary_values():
    """BVA: Budget amount skal være >= 0 (test different amount values)"""
    from backend.shared.schemas.budget import BudgetCreate
    
    today = date.today()
    
    # Valid amounts - test boundary values
    for amount in [0.0, 0.01, 100.0, 1000.0]:
        valid = BudgetCreate(
            amount=amount,
            budget_date=today
        )
        assert abs(valid.amount - amount) < 0.001
    
    # Invalid amount (negative)
    with pytest.raises(ValidationError):
        BudgetCreate(
            amount=-0.01,
            budget_date=today
        )


def test_budget_date_boundary_values():
    """BVA: Budget date validation"""
    from backend.shared.schemas.budget import BudgetCreate
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    
    # Valid budget dates (can be any date - past, present, or future)
    valid = BudgetCreate(
        amount=100.0,
        budget_date=today
    )
    assert valid.budget_date == today
    
    valid = BudgetCreate(
        amount=100.0,
        budget_date=yesterday
    )
    assert valid.budget_date == yesterday
    
    valid = BudgetCreate(
        amount=100.0,
        budget_date=tomorrow
    )
    assert valid.budget_date == tomorrow
    
    # Valid without date (optional)
    valid = BudgetCreate(
        amount=100.0
    )
    assert valid.budget_date is None


# ============================================================================
# GOAL BVA TESTS (4.3)
# ============================================================================

def test_goal_target_amount_boundary_values():
    """BVA: Target amount grænseværdier: -0.01 (invalid), 0 (valid), 0.01 (valid)"""
    from backend.shared.schemas.goal import GoalCreate
    
    # -0.01 - INVALID
    with pytest.raises(ValidationError):
        GoalCreate(
            Account_idAccount=1,
            target_amount=-0.01,
            current_amount=0
        )
    
    # 0 - VALID (grænse)
    valid = GoalCreate(
        Account_idAccount=1,
        target_amount=0.00,
        current_amount=0
    )
    assert abs(valid.target_amount - 0.00) < 0.001
    
    # 0.01 - VALID
    valid = GoalCreate(
        Account_idAccount=1,
        target_amount=0.01,
        current_amount=0
    )
    assert abs(valid.target_amount - 0.01) < 0.001


def test_goal_current_vs_target_boundary():
    """BVA: current_amount må IKKE være > target_amount"""
    from backend.shared.schemas.goal import GoalCreate
    
    # current > target - INVALID
    with pytest.raises(ValidationError):
        GoalCreate(
            Account_idAccount=1,
            target_amount=100,
            current_amount=101
        )
    
    # current = target - VALID (grænse)
    valid = GoalCreate(
        Account_idAccount=1,
        target_amount=100,
        current_amount=100
    )
    assert valid.current_amount == 100
    
    # current < target - VALID
    valid = GoalCreate(
        Account_idAccount=1,
        target_amount=100,
        current_amount=99
    )
    assert valid.current_amount == 99


def test_goal_deadline_boundary_values():
    """BVA: Deadline skal være i fremtiden"""
    from backend.shared.schemas.goal import GoalCreate
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    
    # Dato i fortiden - INVALID
    with pytest.raises(ValidationError):
        GoalCreate(
            Account_idAccount=1,
            target_amount=100,
            current_amount=0,
            target_date=yesterday
        )
    
    # Dato i dag - INVALID
    with pytest.raises(ValidationError):
        GoalCreate(
            Account_idAccount=1,
            target_amount=100,
            current_amount=0,
            target_date=today
        )
    
    # Dato i morgen - VALID (grænse)
    valid = GoalCreate(
        Account_idAccount=1,
        target_amount=100,
        current_amount=0,
        target_date=tomorrow
    )
    assert valid.target_date == tomorrow


# ============================================================================
# TRANSACTION BVA TESTS (4.4)
# ============================================================================

def test_transaction_amount_cannot_be_zero():
    """BVA: Amount må IKKE være 0"""
    from backend.shared.schemas.transaction import TransactionCreate
    
    today = date.today()
    
    # 0 - INVALID
    with pytest.raises(ValidationError):
        TransactionCreate(
            amount=0,
            date=today,
            type="expense",
            category_id=1,
            account_id=1
        )
    
    # -0.01 - VALID (negative/expense)
    valid = TransactionCreate(
        amount=-0.01,
        date=today,
        type="expense",
        category_id=1,
        account_id=1
    )
    assert abs(valid.amount - (-0.01)) < 0.001
    
    # 0.01 - VALID (positive/income)
    valid = TransactionCreate(
        amount=0.01,
        date=today,
        type="income",
        category_id=1,
        account_id=1
    )
    assert abs(valid.amount - 0.01) < 0.001


# ============================================================================
# USER BVA TESTS (4.8)
# ============================================================================

def test_user_username_boundary_values():
    """BVA: Username grænseværdier: 2 (invalid), 3 (valid), 20 (valid), 21 (invalid)"""
    from backend.shared.schemas.user import UserCreate
    
    # 2 chars - INVALID
    with pytest.raises(ValidationError):
        UserCreate(
            username="ab",
            password="ValidPass123",
            email="test@example.com"
        )
    
    # 3 chars - VALID (grænse)
    valid = UserCreate(
        username="abc",
        password="ValidPass123",
        email="test@example.com"
    )
    assert len(valid.username) == 3
    
    # 20 chars - VALID (grænse)
    valid = UserCreate(
        username="a" * 20,
        password="ValidPass123",
        email="test@example.com"
    )
    assert len(valid.username) == 20
    
    # 21 chars - INVALID
    with pytest.raises(ValidationError):
        UserCreate(
            username="a" * 21,
            password="ValidPass123",
            email="test@example.com"
        )


def test_user_password_boundary_values():
    """BVA: Password grænseværdier: 7 (invalid), 8 (valid), 9 (valid)"""
    from backend.shared.schemas.user import UserCreate
    
    # 7 chars - INVALID
    with pytest.raises(ValidationError):
        UserCreate(
            username="validuser",
            password="Pass12",  # kun 6
            email="test@example.com"
        )
    
    # 8 chars - VALID (grænse)
    valid = UserCreate(
        username="validuser",
        password="Pass1234",  # 8 chars
        email="test@example.com"
    )
    assert len(valid.password) >= 8
    
    # 9 chars - VALID
    valid = UserCreate(
        username="validuser",
        password="Pass12345",  # 9 chars
        email="test@example.com"
    )
    assert len(valid.password) >= 8


# ============================================================================
# RUN TESTS
# ============================================================================
# pytest backend/tests/test_bva_validation.py -v
