from sqlalchemy import Column, Integer, String, DECIMAL, ForeignKey, Table, DateTime, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

# Importer Base fra base.py (ingen cirkulær import)
from backend.models.base import Base

class TransactionType(enum.Enum):
    income = "income"
    expense = "expense"

# Association tables
budget_category_association = Table(
    'budget_category_association',
    Base.metadata,
    Column('budget_id', Integer, ForeignKey('Budget.idBudget')),
    Column('category_id', Integer, ForeignKey('Category.idCategory'))
)

account_group_user_association = Table(
    'account_group_user_association',
    Base.metadata,
    Column('account_group_id', Integer, ForeignKey('AccountGroups.idAccountGroups')),
    Column('user_id', Integer, ForeignKey('User.idUser'))
)