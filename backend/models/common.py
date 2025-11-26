# backend/models/common.py

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Enum, ForeignKey, Table, DECIMAL
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base  # Antages at være den korrekte sti til Base
import enum
from datetime import datetime

# --- ENUMS ---
class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"
    
# --- JUNCTION TABLES ---
# Disse defineres her, da de kun refererer til tabelnavne og ikke modelklasser.

budget_category_association = Table(
    'Budget_has_Category',
    Base.metadata,
    Column('Budget_idBudget', Integer, ForeignKey('Budget.idBudget', ondelete='CASCADE'), primary_key=True),
    Column('Category_idCategory', Integer, ForeignKey('Category.idCategory'), primary_key=True),
    extend_existing=True 
)

account_group_user_association = Table(
    'AccountGroups_has_User',
    Base.metadata,
    Column('AccountGroups_idAccountGroups', Integer, ForeignKey('AccountGroups.idAccountGroups', ondelete='CASCADE'), primary_key=True),
    Column('User_idUser', Integer, ForeignKey('User.idUser', ondelete='CASCADE'), primary_key=True),
    extend_existing=True 
)