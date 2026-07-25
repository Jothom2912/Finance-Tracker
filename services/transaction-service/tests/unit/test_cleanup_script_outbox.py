"""P3-20: the duplicate-cleanup script is a participant in the event contract.

``scripts/cleanup_pg_duplicates.py`` deletes straight from transaction-service's
``transactions`` table.  Until 2026-07-26 it did so without writing the
``TransactionDeletedEvent`` that the service's own delete path emits, leaving
rows in the Elasticsearch read model that nothing could ever remove — the row
that would trigger the delete event is already gone, so no retry, replay or
self-healing consumer can notice.  One such phantom (tx 1119, 138,00) inflated
analytics' July figure for account 1, and after P1-13 budget-service reads
spend from exactly that model.

The script lives outside any service package, so it is loaded here by path.
It is tested from transaction-service's suite because that service owns both
the database it writes to and the ``contracts`` dependency it emits — and
because this suite is in the CI matrix, where ``scripts/`` is not.
"""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest
from contracts.events.transaction import TransactionDeletedEvent

_SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "cleanup_pg_duplicates.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("cleanup_pg_duplicates", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    if not _SCRIPT_PATH.exists():  # pragma: no cover - guards a repo-layout change
        pytest.skip(f"cleanup script not found at {_SCRIPT_PATH}")
    return _load_script()


@pytest.fixture
def duplicate_row() -> dict:
    """One row as ``_find_duplicates`` returns it (extra keys included)."""
    return {
        "id": 1119,
        "user_id": 1,
        "account_id": 1,
        "amount": Decimal("138.00"),
        "description": "Aisha ApS",
        "group_size": 2,
        "keep_id": 1118,
    }


class _FakeCursor:
    """Records statements in order so we can assert insert-before-delete."""

    def __init__(self, *, deleted: int, inserted: int | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self._deleted = deleted
        self._inserted = inserted
        self.rowcount = 0

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def executemany(self, sql: str, params: list) -> None:
        self.calls.append(("executemany", sql))
        self.rowcount = self._inserted if self._inserted is not None else len(params)
        self.params = params

    def execute(self, sql: str, params: object = None) -> None:
        self.calls.append(("execute", sql))
        self.rowcount = self._deleted


class _FakeConn:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def test_outbox_row_payload_parses_back_as_the_contract_event(script, duplicate_row):
    """The payload is built from the real contract class, so it round-trips.

    This is the whole point of importing ``TransactionDeletedEvent`` instead of
    hand-building JSON: a new required field on the contract breaks here rather
    than shipping a payload consumers silently cannot parse.
    """
    row = script._build_outbox_row(duplicate_row)
    _id, aggregate_type, aggregate_id, event_type, payload_json, correlation_id, status, attempts = row

    event = TransactionDeletedEvent.from_json(payload_json)

    assert event.transaction_id == 1119
    assert event.account_id == 1
    assert event.user_id == 1
    assert event.amount == "138.00"  # string, so Decimal precision survives the wire
    assert event.event_type == "transaction.deleted"


def test_outbox_row_matches_the_columns_the_publisher_polls(script, duplicate_row):
    """Column values must match ``OutboxRepository._build`` or the row is never picked up."""
    row = script._build_outbox_row(duplicate_row)
    _id, aggregate_type, aggregate_id, event_type, payload_json, correlation_id, status, attempts = row

    assert aggregate_type == "transaction"
    assert aggregate_id == "1119"
    # The worker derives the routing key from event_type — a wrong value here
    # publishes to a routing key no queue is bound to, and the event vanishes.
    assert event_type == "transaction.deleted"
    assert status == "pending"
    assert attempts == 0
    assert correlation_id == json.loads(payload_json)["correlation_id"]
    assert len(_id) == 36  # uuid4, matching the varchar(36) primary key


def test_each_row_gets_its_own_event_id_and_aggregate(script, duplicate_row):
    other = {**duplicate_row, "id": 1024, "amount": Decimal("120.00")}

    first = script._build_outbox_row(duplicate_row)
    second = script._build_outbox_row(other)

    assert first[0] != second[0]
    assert (first[2], second[2]) == ("1119", "1024")


def test_events_are_inserted_before_the_delete_and_committed_once(script, duplicate_row):
    """Insert first: a failing DELETE then rolls the events back with it."""
    cursor = _FakeCursor(deleted=1)
    conn = _FakeConn(cursor)

    deleted = script._delete_rows(conn, [duplicate_row])

    assert deleted == 1
    kinds = [kind for kind, _ in cursor.calls]
    assert kinds == ["executemany", "execute"], "outbox insert must precede the DELETE"
    assert "INSERT INTO outbox_events" in cursor.calls[0][1]
    assert "DELETE FROM transactions" in cursor.calls[1][1]
    assert conn.committed and not conn.rolled_back


def test_row_count_divergence_rolls_back_instead_of_committing(script, duplicate_row):
    """The failure this guard exists for: a delete event for a row still alive.

    If the DELETE matches fewer rows than we outboxed events for (concurrent
    delete, a WHERE that stopped matching), committing would tell the read
    model a live transaction is gone — the inverse of the bug being fixed, and
    just as unrecoverable, since ``is_deleted`` is terminal in ES.
    """
    cursor = _FakeCursor(deleted=0, inserted=1)
    conn = _FakeConn(cursor)

    with pytest.raises(RuntimeError, match="Refusing to commit"):
        script._delete_rows(conn, [duplicate_row])

    assert conn.rolled_back and not conn.committed
