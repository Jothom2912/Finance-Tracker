from __future__ import annotations

import enum

from contracts.base import BaseEvent


class SyncTrigger(str, enum.Enum):
    """What caused a bank sync to run.

    Consumers use this to tell a user-initiated sync (which always deserves a
    receipt, even when nothing changed) from the nightly sweep (which should
    stay quiet unless it has something to report).
    """

    MANUAL = "manual"
    SCHEDULED = "scheduled"


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
    # Additive with a default, so event_version stays 1: payloads already sitting
    # in an outbox or queue at deploy time still validate. The default is MANUAL
    # rather than SCHEDULED because this field gates whether a user hears about
    # something -- unknown provenance should err toward telling them.
    trigger: SyncTrigger = SyncTrigger.MANUAL
