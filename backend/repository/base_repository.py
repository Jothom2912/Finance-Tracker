# backend/repository/base_repository.py
"""
Base repository interfaces - Import from backend.repositories.base for consistency
"""
# Import interfaces from the main repositories module to match MySQL implementations
from backend.repositories.base import (
    ITransactionRepository,
    ICategoryRepository,
    IAccountRepository,
    IUserRepository,
    IBudgetRepository
)

# Re-export for convenience
__all__ = [
    "ITransactionRepository",
    "ICategoryRepository",
    "IAccountRepository",
    "IUserRepository",
    "IBudgetRepository"
]
