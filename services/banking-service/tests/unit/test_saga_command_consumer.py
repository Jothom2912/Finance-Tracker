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
from app.models.processed_events import ProcessedEventModel
from app.workers.saga_command_consumer import BankingSagaCommandConsumer
from contracts.events.bank import SyncTrigger
from sqlalchemy.exc import IntegrityError


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


class _Result:
    def __init__(self, row) -> None:
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeSession:
    """Minimal async-session-stand-in for _handle_mark_sync_complete.

    Skelner de to SELECTs handleren laver (bank_connections vs.
    processed_events) på statementets entity, og *persisterer* inbox-rækker
    ved commit — så et andet kald mod samme session-tilstand ser den række
    det første kald skrev. Uden den persistering ville en redelivery-test
    bestå vakuøst.
    """

    def __init__(self, conn, inbox: set[str] | None = None, fail_commit: bool = False) -> None:
        self._conn = conn
        self.inbox: set[str] = inbox if inbox is not None else set()
        self.added: list = []
        self.committed = False
        self.commit_count = 0
        self.rollback_count = 0
        self._fail_commit = fail_commit

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def execute(self, stmt, *_args, **_kwargs):
        if stmt.column_descriptions[0]["entity"] is ProcessedEventModel:
            asked = set(stmt.compile().params.values())
            return _Result(object() if asked & self.inbox else None)
        return _Result(self._conn)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commit_count += 1
        if self._fail_commit:
            # Efterlign unique-constraint'en: kapløbstaberen ser den her.
            raise IntegrityError("uq_processed_event", None, Exception("duplicate key"))
        self.committed = True
        for obj in self.added:
            if isinstance(obj, ProcessedEventModel):
                self.inbox.add(obj.correlation_id)
        self.added = []

    async def rollback(self) -> None:
        self.rollback_count += 1
        self.added = []


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


async def _call_mark_sync_complete(conn, body: dict, session: _FakeSession | None = None):
    """Kør handleren én gang; returnér (reply, outbox_add_mock, session).

    Rå variant: siger intet om at der *blev* emitteret et event — det er
    netop det dublet-testene skal kunne se.
    """
    consumer = BankingSagaCommandConsumer()
    session = session if session is not None else _FakeSession(conn)
    with (
        patch("app.workers.saga_command_consumer.async_session_factory", lambda: session),
        patch("app.workers.saga_command_consumer.OutboxRepository") as outbox_cls,
    ):
        outbox_cls.return_value.add = AsyncMock()
        reply = await consumer._handle_mark_sync_complete(body)
    return reply, outbox_cls.return_value.add, session


async def _run_mark_sync_complete(conn, body: dict):
    """Kør handleren; returnér det emitterede BankSyncCompletedEvent."""
    reply, add_mock, session = await _call_mark_sync_complete(conn, body)
    assert reply == {"success": True}
    assert session.committed
    return add_mock.await_args.kwargs["event"]


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


# ── P2-22: inbox-guard på mark_sync_complete ─────────────────────────


def _command(conn, saga_id: str = "saga-1", step_name: str = "mark_sync_complete") -> dict:
    return {
        "connection_id": str(conn.id),
        "user_id": 2,
        "saga_id": saga_id,
        "step_name": step_name,
    }


@pytest.mark.asyncio
async def test_redelivered_command_emits_no_second_event() -> None:
    # Hele P2-22 i én test. Første levering rydder claimet; anden levering
    # ville derfor læse sync_trigger=NULL → MANUAL → et ANDET
    # BankSyncCompletedEvent med frisk correlation_id, hvis source_key-dedup
    # i notification-service ikke kan absorbere → spøgelsesnotifikation.
    conn = _connection_row(saga_id="saga-1", sync_trigger="scheduled")
    session = _FakeSession(conn)

    first_reply, first_add, _ = await _call_mark_sync_complete(conn, _command(conn), session)
    second_reply, second_add, _ = await _call_mark_sync_complete(conn, _command(conn), session)

    assert first_add.await_count == 1
    assert second_add.await_count == 0, "redelivery emitterede et andet completion-event"
    # Og begge svarer — se næste test for hvorfor det er afgørende.
    assert first_reply == {"success": True}
    assert second_reply == {"success": True}


@pytest.mark.asyncio
async def test_duplicate_still_replies_so_the_saga_does_not_hang() -> None:
    # Grunden til redeliveryen er typisk at reply'et blev tabt. Ack'er vi
    # dubletten uden at svare, hænger sagaen til timeout og går i
    # kompensation — vi ville bytte en spøgelsesnotifikation for en fejlet
    # saga. Dublet-stien skal derfor svare success, ikke tie.
    conn = _connection_row(saga_id="saga-1", sync_trigger="manual")
    session = _FakeSession(conn, inbox={"saga-1:mark_sync_complete"})

    reply, add_mock, _ = await _call_mark_sync_complete(conn, _command(conn), session)

    assert reply == {"success": True}
    assert add_mock.await_count == 0
    assert session.commit_count == 0, "dublet-stien må ikke skrive noget"


@pytest.mark.asyncio
async def test_two_steps_in_the_same_saga_both_run() -> None:
    # Nøglen er (saga_id, step_name) — ikke saga_id alene. Var den saga_id
    # alene, ville trin 2 blive afvist som dublet af trin 1 og hele sagaen
    # standse. Nem fejl at lave, og den ville se ud som en "hængende saga".
    conn = _connection_row(saga_id="saga-1", sync_trigger="scheduled")
    session = _FakeSession(conn)

    _, first_add, _ = await _call_mark_sync_complete(conn, _command(conn, step_name="fetch_transactions"), session)
    _, second_add, _ = await _call_mark_sync_complete(conn, _command(conn, step_name="mark_sync_complete"), session)

    assert first_add.await_count == 1
    assert second_add.await_count == 1


@pytest.mark.asyncio
async def test_inbox_row_commits_with_the_effects() -> None:
    # Inbox-rækken skal ligge i handlerens egen transaktion. Ét commit,
    # der bærer både claim-ryddet, outbox-rækken og inbox-rækken.
    conn = _connection_row(saga_id="saga-1", sync_trigger="scheduled")
    session = _FakeSession(conn)

    await _call_mark_sync_complete(conn, _command(conn), session)

    assert session.commit_count == 1
    assert session.inbox == {"saga-1:mark_sync_complete"}


@pytest.mark.asyncio
async def test_integrity_error_on_commit_is_a_benign_race() -> None:
    # To deliveries samtidigt: exists-checket var rent i begge, og
    # unique-constraint'en afgjorde kapløbet. Taberen ruller tilbage og
    # svarer som dublet i stedet for at fejle sagaen.
    conn = _connection_row(saga_id="saga-1", sync_trigger="scheduled")
    session = _FakeSession(conn, fail_commit=True)

    reply, _, _ = await _call_mark_sync_complete(conn, _command(conn), session)

    assert reply == {"success": True}
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_command_without_step_name_runs_without_guard(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # En delvis nøgle er farligere end ingen: ":" ville matche hver anden
    # nøgleløs kommando og gøre alle på nær den første til dubletter. Vi
    # falder tilbage til adfærden fra før guarden — og siger det højt.
    conn = _connection_row(saga_id="saga-1", sync_trigger="scheduled")
    session = _FakeSession(conn)

    with caplog.at_level(logging.WARNING):
        _, add_mock, _ = await _call_mark_sync_complete(
            conn, {"connection_id": str(conn.id), "user_id": 2, "saga_id": "saga-1"}, session
        )

    assert add_mock.await_count == 1
    assert session.inbox == set()
    assert "uden inbox-guard" in caplog.text
