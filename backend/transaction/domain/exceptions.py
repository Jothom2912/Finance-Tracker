"""
Domain exceptions for Transaction bounded context.
These represent business rule violations.
"""


class TransactionException(Exception):
    """Base exception for transaction domain."""
    pass


class TransactionNotFound(TransactionException):
    """Raised when transaction doesn't exist."""
    def __init__(self, transaction_id: int):
        self.transaction_id = transaction_id
        super().__init__(f"Transaction with ID {transaction_id} not found")


class InvalidTransactionAmount(TransactionException):
    """Raised when amount is invalid (e.g. zero)."""
    pass


class CategoryNotFound(TransactionException):
    """Raised when category doesn't exist."""
    def __init__(self, category_id: int):
        self.category_id = category_id
        super().__init__(f"Category with ID {category_id} not found")


class AccountRequired(TransactionException):
    """Raised when account_id is missing."""
    pass


class PlannedTransactionRepositoryNotConfigured(TransactionException):
    """Raised when planned transaction repo is not injected."""
    pass
