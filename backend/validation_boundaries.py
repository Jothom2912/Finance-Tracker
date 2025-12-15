# backend/validation_boundaries.py
"""
Centraliseret definition af Boundary Value Analysis (BVA) constraints.
Dette modul definerer alle grænseværdier for validering af entities.
"""

from dataclasses import dataclass
from typing import Tuple
from decimal import Decimal

# ============================================================================
# CATEGORY - Grænseværdier (4.1)
# ============================================================================
@dataclass
class CategoryBoundaries:
    name_min_length: int = 5
    name_max_length: int = 30
    description_max_length: int = 200
    valid_types: Tuple[str, ...] = ("income", "expense")


# ============================================================================
# BUDGET - Grænseværdier (4.2)
# ============================================================================
@dataclass
class BudgetBoundaries:
    amount_min: Decimal = Decimal("0.00")  # Must be >= 0
    valid_periods: Tuple[str, ...] = ("weekly", "monthly", "yearly")
    # Datoer: start < end


# ============================================================================
# GOAL - Grænseværdier (4.3)
# ============================================================================
@dataclass
class GoalBoundaries:
    target_amount_min: Decimal = Decimal("0.00")  # >= 0
    current_amount_min: Decimal = Decimal("0.00")  # >= 0
    # Logik: targetAmount >= currentAmount


# ============================================================================
# TRANSACTION - Grænseværdier (4.4)
# ============================================================================
@dataclass
class TransactionBoundaries:
    amount_cannot_be_zero: bool = True  # amount != 0
    # amount kan være positiv eller negativ


# ============================================================================
# PLANNED_TRANSACTION - Grænseværdier (4.5)
# ============================================================================
@dataclass
class PlannedTransactionBoundaries:
    amount_cannot_be_zero: bool = True  # amount != 0
    valid_intervals: Tuple[str, ...] = ("daily", "weekly", "monthly")
    # planned_date: future or current (ikke fortid)


# ============================================================================
# ACCOUNT - Grænseværdier (4.6)
# ============================================================================
@dataclass
class AccountBoundaries:
    name_min_length: int = 1
    name_max_length: int = 30
    # balance: kan være negativ eller positiv


# ============================================================================
# USER - Grænseværdier (4.8)
# ============================================================================
@dataclass
class UserBoundaries:
    username_min_length: int = 3
    username_max_length: int = 20
    password_min_length: int = 8
    email_pattern: str = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


# ============================================================================
# ACCOUNT_GROUP - Grænseværdier (4.7)
# ============================================================================
@dataclass
class AccountGroupBoundaries:
    name_min_length: int = 1
    name_max_length: int = 30
    max_users: int = 20


# ============================================================================
# Helper instances for easy import
# ============================================================================
CATEGORY_BVA = CategoryBoundaries()
BUDGET_BVA = BudgetBoundaries()
GOAL_BVA = GoalBoundaries()
TRANSACTION_BVA = TransactionBoundaries()
PLANNED_TRANSACTION_BVA = PlannedTransactionBoundaries()
ACCOUNT_BVA = AccountBoundaries()
USER_BVA = UserBoundaries()
ACCOUNT_GROUP_BVA = AccountGroupBoundaries()
