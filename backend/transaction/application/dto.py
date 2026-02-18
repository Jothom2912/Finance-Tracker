"""
Data Transfer Objects for transaction use cases.
These cross the boundary between adapters and application.

Re-exports shared Pydantic schemas as application DTO aliases.
"""
from backend.shared.schemas.transaction import (
    TransactionCreate as TransactionCreateDTO,
    Transaction as TransactionResponseDTO,
    TransactionType as TransactionTypeDTO,
)
from backend.shared.schemas.planned_transactions import (
    PlannedTransactionsCreate as PlannedTransactionCreateDTO,
    PlannedTransactionsBase as PlannedTransactionUpdateDTO,
    PlannedTransactions as PlannedTransactionResponseDTO,
)

__all__ = [
    "TransactionCreateDTO",
    "TransactionResponseDTO",
    "TransactionTypeDTO",
    "PlannedTransactionCreateDTO",
    "PlannedTransactionUpdateDTO",
    "PlannedTransactionResponseDTO",
]
