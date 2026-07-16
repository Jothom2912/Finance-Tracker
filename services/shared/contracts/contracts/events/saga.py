from __future__ import annotations

from typing import Any

from contracts.base import BaseEvent


class SagaCommand(BaseEvent):
    """Command issued by saga orchestrator to a participant service."""

    saga_id: str
    saga_type: str
    step_name: str


class SagaReply(BaseEvent):
    """Reply from a participant service back to the saga orchestrator."""

    event_type: str = "saga.reply"
    saga_id: str
    step_name: str
    success: bool
    error_message: str | None = None
    result_data: dict[str, Any] | None = None
    is_compensation: bool = False


class BankFetchTransactionsCommand(SagaCommand):
    """Command to banking-service: fetch transactions from bank API."""

    event_type: str = "saga.cmd.bank_fetch_transactions"
    connection_id: str
    user_id: int
    date_from: str | None = None


class BulkImportTransactionsCommand(SagaCommand):
    """Command to transaction-service: bulk import fetched transactions.

    ``items`` is deliberately untyped — the saga round-trips it through
    JSON context, so a typed model here would never be instantiated on
    the consume path.  Item shape (producer: banking-service's fetch
    handler; consumer: transaction-service's bulk-import handler)::

        {
            "amount": str,               # abs value, Decimal-parseable
            "transaction_type": str,     # "income" | "expense"
            "date": str,                 # ISO date
            "description": str,
            "external_id": str | None,   # EB entry_reference (P2-09)
            "currency": str,             # ISO 4217, default "DKK"
        }

    Consumers MUST read item keys with ``.get()`` and defaults so old
    in-flight messages (or not-yet-redeployed producers) keep working.
    """

    event_type: str = "saga.cmd.bulk_import_transactions"
    user_id: int
    account_id: int
    account_name: str
    items: list[dict[str, Any]]


class MarkSyncCompleteCommand(SagaCommand):
    """Command to banking-service: mark sync as completed."""

    event_type: str = "saga.cmd.mark_sync_complete"
    connection_id: str
    user_id: int
    total_fetched: int
    new_imported: int
    duplicates_skipped: int
    errors: int


class RollbackImportCommand(SagaCommand):
    """Compensation command to transaction-service: soft-delete imported transactions."""

    event_type: str = "saga.cmd.rollback_import"
    user_id: int
    transaction_ids: list[int]


class BankSyncSagaStartEvent(BaseEvent):
    """Published by banking-service to initiate a bank sync saga."""

    event_type: str = "saga.bank_sync.start"
    saga_type: str = "bank_sync"
    connection_id: str
    user_id: int
    account_id: int
    account_name: str
    bank_account_uid: str
    date_from: str | None = None


class BankSyncSagaCompletedEvent(BaseEvent):
    """Published when a bank sync saga completes successfully."""

    event_type: str = "saga.bank_sync.completed"
    saga_id: str
    connection_id: str
    user_id: int
    new_imported: int
    errors: int
