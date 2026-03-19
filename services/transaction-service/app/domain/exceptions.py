from __future__ import annotations


class TransactionNotFoundException(Exception):
    def __init__(self, transaction_id: int) -> None:
        self.transaction_id = transaction_id
        super().__init__(f"Transaction {transaction_id} not found")


class PlannedTransactionNotFoundException(Exception):
    def __init__(self, planned_id: int) -> None:
        self.planned_id = planned_id
        super().__init__(f"Planned transaction {planned_id} not found")


class InvalidTransactionException(Exception):
    pass


class CSVImportException(Exception):
    pass


class CategoryNotFoundException(Exception):
    def __init__(self, category_id: int) -> None:
        self.category_id = category_id
        super().__init__(f"Category {category_id} not found")


class DuplicateCategoryNameException(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Category with name '{name}' already exists")


class CategoryInUseException(Exception):
    """Raised when attempting to delete a category that is still referenced."""

    def __init__(self, category_id: int) -> None:
        self.category_id = category_id
        super().__init__(
            f"Category {category_id} cannot be deleted because it is "
            "referenced by existing transactions"
        )
