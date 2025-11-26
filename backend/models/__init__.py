# backend/models/__init__.py

# Importer alt nødvendigt fra common, FØR modellerne importeres.
from .common import (
    Base, 
    TransactionType, 
    budget_category_association, 
    account_group_user_association
)

# --- SAMLENDE IMPORTS (SKAL INDLÆSES SIDST) ---
# Disse linjer udløser indlæsningen af alle de individuelle model-filer.
from .user import User
from .category import Category
from .account import Account
from .transaction import Transaction
from .budget import Budget
from .goal import Goal
from .planned_transactions import PlannedTransactions
from .account_groups import AccountGroups