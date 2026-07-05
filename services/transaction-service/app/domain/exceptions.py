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
