"""Unit tests for ``BankingSagaCommandConsumer._handle_fetch_transactions``.

First coverage of the saga item contract (P2-09): until now nothing
locked the shape of the item dicts banking hands to the saga — the
audit's H10 (entry_reference/currency silently dropped) lived exactly
in that gap.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.adapters.outbound.enable_banking_client import BankTransaction
from app.workers.saga_command_consumer import BankingSagaCommandConsumer
from contracts.events.bank import SyncTrigger


def _bank_txn(**overrides) -> BankTransaction:  # type: ignore[no-untyped-def]
    defaults = {
        "transaction_id": "EB-REF-1",
        "amount": Decimal("-49.99"),
        "currency": "DKK",
        "description": "Netto",
        "date": date(2026, 3, 1),
    }
    defaults.update(overrides)
    return BankTransaction(**defaults)


async def _fetch_items(transactions: list[BankTransaction]) -> list[dict]:
    consumer = BankingSagaCommandConsumer()
    client = AsyncMock()
    client.get_transactions.return_value = (transactions, 0)
    consumer._banking_client = client

    with patch.object(consumer, "_reject_if_consent_expired", AsyncMock(return_value=None)):
        reply = await consumer._handle_fetch_transactions(
            {"connection_id": str(uuid4()), "bank_account_uid": "acc-1"},
        )

    assert reply["success"] is True
    return reply["result_data"]["items"]


@pytest.mark.asyncio
async def test_items_carry_external_id_and_currency() -> None:
    items = await _fetch_items(
        [
            _bank_txn(transaction_id="EB-REF-1", currency="DKK"),
            _bank_txn(transaction_id="EB-REF-2", currency="EUR", amount=Decimal("100.00")),
        ],
    )

    assert [i["external_id"] for i in items] == ["EB-REF-1", "EB-REF-2"]
    assert [i["currency"] for i in items] == ["DKK", "EUR"]


@pytest.mark.asyncio
async def test_blank_transaction_id_maps_to_none_external_id() -> None:
    """ ""/whitespace entry_references must never reach transaction-service
    as dedup keys — normalize to None so it falls back to the fuzzy key."""
    items = await _fetch_items(
        [_bank_txn(transaction_id=""), _bank_txn(transaction_id="   ")],
    )

    assert [i["external_id"] for i in items] == [None, None]


@pytest.mark.asyncio
async def test_missing_currency_defaults_to_dkk() -> None:
    items = await _fetch_items([_bank_txn(currency="")])

    assert items[0]["currency"] == "DKK"


@pytest.mark.asyncio
async def test_existing_mapping_contract_unchanged() -> None:
    """Locks the pre-P2-09 item fields: abs amount as string, sign folded
    into transaction_type, ISO date, description verbatim."""
    items = await _fetch_items(
        [
            _bank_txn(amount=Decimal("-49.99"), description="Netto"),
            _bank_txn(transaction_id="EB-REF-2", amount=Decimal("15000.00"), description="Løn"),
        ],
    )

    assert items[0]["amount"] == "49.99"
    assert items[0]["transaction_type"] == "expense"
    assert items[0]["date"] == "2026-03-01"
    assert items[0]["description"] == "Netto"
    assert items[1]["amount"] == "15000.00"
    assert items[1]["transaction_type"] == "income"


# ── P3-14: mark_sync_complete frigiver sync-claimet ──────────────────


class _FakeSession:
    """Minimal async-session-stand-in for _handle_mark_sync_complete."""

    def __init__(self, conn) -> None:
        self._conn = conn
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def execute(self, *_args, **_kwargs):
        conn = self._conn

        class _Result:
            @staticmethod
            def scalar_one_or_none():
                return conn

        return _Result()

    async def commit(self) -> None:
        self.committed = True


def _connection_row(saga_id: str | None, sync_trigger: str | None = None):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=uuid4(),
        account_id=1,
        last_synced_at=None,
        sync_saga_id=saga_id,
        sync_started_at=object(),
        sync_trigger=sync_trigger,
    )


async def _run_mark_sync_complete(conn, body: dict):
    """Kør handleren; returnér det emitterede BankSyncCompletedEvent."""
    consumer = BankingSagaCommandConsumer()
    session = _FakeSession(conn)
    with (
        patch("app.workers.saga_command_consumer.async_session_factory", lambda: session),
        patch("app.workers.saga_command_consumer.OutboxRepository") as outbox_cls,
    ):
        outbox_cls.return_value.add = AsyncMock()
        reply = await consumer._handle_mark_sync_complete(body)
    assert reply == {"success": True}
    assert session.committed
    return outbox_cls.return_value.add.await_args.kwargs["event"]


@pytest.mark.asyncio
async def test_mark_sync_complete_clears_matching_claim() -> None:
    conn = _connection_row(saga_id="saga-1", sync_trigger="scheduled")

    await _run_mark_sync_complete(
        conn,
        {"connection_id": str(conn.id), "user_id": 2, "saga_id": "saga-1"},
    )

    assert conn.sync_saga_id is None
    assert conn.sync_started_at is None
    assert conn.sync_trigger is None
    assert conn.last_synced_at is not None


@pytest.mark.asyncio
async def test_mark_sync_complete_leaves_newer_claim_untouched() -> None:
    # En gammel/duplikeret reply maa ikke rydde en NYERE sagas claim.
    conn = _connection_row(saga_id="newer-saga", sync_trigger="manual")

    await _run_mark_sync_complete(
        conn,
        {"connection_id": str(conn.id), "user_id": 2, "saga_id": "old-saga"},
    )

    assert conn.sync_saga_id == "newer-saga"
    assert conn.sync_started_at is not None
    assert conn.sync_trigger == "manual"
    assert conn.last_synced_at is not None


@pytest.mark.asyncio
async def test_sync_trigger_is_read_from_the_claim_before_it_is_cleared() -> None:
    # Claimet er triggerens eneste bærer, og den samme handler rydder det.
    # Læses den efter rydningen, bliver hver scheduled sync til "manual" og
    # hele undertrykkelsen i notification-service holder op med at virke.
    conn = _connection_row(saga_id="saga-1", sync_trigger="scheduled")

    event = await _run_mark_sync_complete(
        conn,
        {"connection_id": str(conn.id), "user_id": 2, "saga_id": "saga-1"},
    )

    assert event.trigger is SyncTrigger.SCHEDULED
    assert conn.sync_trigger is None


@pytest.mark.asyncio
async def test_null_sync_trigger_falls_back_to_manual() -> None:
    # Rækker claimet før migration 004. Fallback skal være MANUAL, så en
    # ukendt provenance fejler i retning af at fortælle brugeren noget.
    conn = _connection_row(saga_id="saga-1", sync_trigger=None)

    event = await _run_mark_sync_complete(
        conn,
        {"connection_id": str(conn.id), "user_id": 2, "saga_id": "saga-1"},
    )

    assert event.trigger is SyncTrigger.MANUAL


@pytest.mark.asyncio
async def test_unknown_sync_trigger_falls_back_to_manual_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Fallback'en er rigtig, men den skjuler et bug-signal: en writer er ude af
    # sync med enum'en, og symptomet (klokken bliver støjende) peger ikke på
    # årsagen. Derfor SKAL den logge — modsat NULL-tilfældet nedenfor.
    conn = _connection_row(saga_id="saga-1", sync_trigger="cron")

    with caplog.at_level(logging.WARNING):
        event = await _run_mark_sync_complete(
            conn,
            {"connection_id": str(conn.id), "user_id": 2, "saga_id": "saga-1"},
        )

    assert event.trigger is SyncTrigger.MANUAL
    assert "cron" in caplog.text


@pytest.mark.asyncio
async def test_null_sync_trigger_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    # NULL er forventet (rækker claimet før migration 004) — ingen støj.
    conn = _connection_row(saga_id="saga-1", sync_trigger=None)

    with caplog.at_level(logging.WARNING):
        await _run_mark_sync_complete(
            conn,
            {"connection_id": str(conn.id), "user_id": 2, "saga_id": "saga-1"},
        )

    assert "sync_trigger" not in caplog.text


@pytest.mark.asyncio
async def test_foreign_claim_is_never_read_as_scheduled() -> None:
    # Kernen i fejlen: claim-rækken er ikke versioneret per saga, så en nyere
    # saga kan have overskrevet sync_trigger mens vi kørte. En LANGSOM MANUEL
    # sync ville da blive stemplet "scheduled" og undertrykt af
    # notification-service — brugeren trykkede på knappen og fik stilhed.
    # Fremmed claim ⇒ MANUAL, altid.
    conn = _connection_row(saga_id="sweep-saga", sync_trigger="scheduled")

    event = await _run_mark_sync_complete(
        conn,
        {"connection_id": str(conn.id), "user_id": 2, "saga_id": "stalled-manual-saga"},
    )

    assert event.trigger is SyncTrigger.MANUAL
    # Og det fremmede claim står stadig urørt.
    assert conn.sync_trigger == "scheduled"
    assert conn.sync_saga_id == "sweep-saga"


@pytest.mark.asyncio
async def test_missing_saga_id_in_body_is_not_treated_as_our_claim() -> None:
    # Uden saga_id kan vi ikke bevise ejerskab, så vi må ikke låne claimets
    # trigger — heller ikke selvom værdien tilfældigvis ser rigtig ud.
    conn = _connection_row(saga_id="sweep-saga", sync_trigger="scheduled")

    event = await _run_mark_sync_complete(conn, {"connection_id": str(conn.id), "user_id": 2})

    assert event.trigger is SyncTrigger.MANUAL
