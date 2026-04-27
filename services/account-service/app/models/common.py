# backend/models/common.py

import enum
from datetime import datetime  # noqa: F401

from sqlalchemy import (  # noqa: F401
    DECIMAL,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
)
from sqlalchemy.orm import relationship  # noqa: F401
from sqlalchemy.sql import func  # noqa: F401

from app.mysql import Base  # noqa: F401


# --- ENUMS ---
class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"


# --- JUNCTION TABLES ---
# Disse defineres her, da de kun refererer til tabelnavne og ikke modelklasser.

budget_category_association = Table(
    "Budget_has_Category",
    Base.metadata,
    Column("Budget_idBudget", Integer, ForeignKey("Budget.idBudget", ondelete="CASCADE"), primary_key=True),
    Column("Category_idCategory", Integer, ForeignKey("Category.idCategory"), primary_key=True),
    extend_existing=True,
)

account_group_user_association = Table(
    "AccountGroups_has_User",
    Base.metadata,
    Column(
        "AccountGroups_idAccountGroups",
        Integer,
        ForeignKey("AccountGroups.idAccountGroups", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("User_idUser", Integer, primary_key=True),
    extend_existing=True,
)
