from __future__ import annotations

from contracts.base import BaseEvent


class BankConnectionCreatedEvent(BaseEvent):
    event_type: str = "bank.connection.created"
    event_version: int = 1
    connection_id: str
    account_id: int
    user_id: int
    bank_name: str
    iban: str | None = None
    status: str = "new"


class BankConnectionDisconnectedEvent(BaseEvent):
    event_type: str = "bank.connection.disconnected"
    event_version: int = 1
    connection_id: str
    account_id: int
    user_id: int
    bank_name: str
    iban: str | None = None


class BankSyncCompletedEvent(BaseEvent):
    event_type: str = "bank.sync.completed"
    event_version: int = 1
    connection_id: str
    account_id: int
    user_id: int
    total_fetched: int
    new_imported: int
    duplicates_skipped: int
    errors: int
    parse_skipped: int = 0
