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


class SubcategoryNotFoundException(Exception):
    def __init__(self, subcategory_id: int) -> None:
        self.subcategory_id = subcategory_id
        super().__init__(f"Subcategory {subcategory_id} not found")


class SubcategoryMismatchException(Exception):
    """Raised when a chosen subcategory does not belong to the chosen category."""

    def __init__(self, subcategory_id: int, category_id: int | None) -> None:
        self.subcategory_id = subcategory_id
        self.category_id = category_id
        super().__init__(f"Subcategory {subcategory_id} does not belong to category {category_id}")
