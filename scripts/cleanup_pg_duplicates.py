"""One-off cleanup: remove duplicate transactions from PostgreSQL.

Duplicates are identified by the dedup key used in bulk_import:
(user_id, account_id, date, amount, description). For each group
of duplicates, the row with the lowest id (oldest) is kept.

amount is Numeric(12,2) — safe for equality matching.

Safety rails
------------
* **--dry-run is the default.**  Shows counts and sample groups.
* **--execute** must be passed explicitly to delete.
* FK constraints are checked before any delete attempt.
* SELECT + DELETE run in a single transaction to prevent races.
* Every deleted row is logged as full JSON for audit.
* Idempotent — running twice is safe (second run finds 0 duplicates).

Event contract (P3-20)
----------------------
Deleting straight from ``transactions`` is only half the service's own
delete path: ``TransactionService.delete_transaction`` writes a
``TransactionDeletedEvent`` outbox row *in the same transaction* so the
Elasticsearch read model learns about it.  A script that skips that step
leaves a phantom row nothing can ever remove — the row that would trigger
the event is already gone, so no retry, replay or self-healing consumer
can notice (see ``dev-notes/findings/2026-07-25-cleanup-script-desyncs-read-model.md``).

So this script writes the same outbox rows in the same transaction as its
DELETE, and the existing transaction-outbox-publisher does the rest.
The event object is imported from ``contracts`` rather than hand-built as
JSON, so the payload cannot drift from the contract.

Usage::

    # Dry run (default) — see what would be deleted
    uv run --project services/transaction-service python scripts/cleanup_pg_duplicates.py

    # Actually delete
    uv run --project services/transaction-service python scripts/cleanup_pg_duplicates.py --execute

``--project services/transaction-service`` is required, not cosmetic: there
is no root pyproject, and that venv is the one that owns both the psycopg2
driver and ``contracts`` as a path dependency.  It is also the right venv on
principle — this script writes to transaction-service's database.

Environment variables::

    TRANSACTION_SERVICE_DB_URL   PostgreSQL connection (transaction-service)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _REPO_ROOT / ".env"

from dotenv import load_dotenv

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PG_URL = os.getenv(
    "TRANSACTION_SERVICE_DB_URL",
    "postgresql://transaction_service:transaction_service_pass@localhost:5434/transactions",
)

BACKUP_DIR = _REPO_ROOT / "scripts" / "backups"


class _Encoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return super().default(o)


def _get_connection():
    import psycopg2

    url = PG_URL
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        url = url.replace(prefix, "postgresql://")
    return psycopg2.connect(url)


def _check_fk_constraints(conn) -> list[str]:
    """Check for foreign keys referencing the transactions table."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT conname, conrelid::regclass
            FROM pg_constraint
            WHERE confrelid = 'transactions'::regclass
        """)
        return [(row[0], str(row[1])) for row in cur.fetchall()]


def _find_duplicates(conn) -> list[dict]:
    """Find duplicate groups and return rows to delete (all but lowest id per group)."""
    with conn.cursor() as cur:
        cur.execute("""
            WITH dupes AS (
                SELECT
                    user_id, account_id, date, amount, description,
                    COUNT(*) AS cnt,
                    MIN(id) AS keep_id
                FROM transactions
                GROUP BY user_id, account_id, date, amount, description
                HAVING COUNT(*) > 1
            )
            SELECT
                t.id, t.user_id, t.account_id, t.date, t.amount,
                t.description, t.category_id, t.category_name,
                t.subcategory_id, t.categorization_tier, t.created_at,
                d.cnt AS group_size, d.keep_id
            FROM transactions t
            JOIN dupes d ON
                t.user_id = d.user_id
                AND t.account_id = d.account_id
                AND t.date = d.date
                AND t.amount = d.amount
                AND (t.description = d.description OR (t.description IS NULL AND d.description IS NULL))
            WHERE t.id != d.keep_id
            ORDER BY d.keep_id, t.id
        """)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def _get_summary(conn) -> dict:
    """Get overall transaction count and duplicate group stats."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM transactions")
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM transactions
                GROUP BY user_id, account_id, date, amount, description
                HAVING COUNT(*) > 1
            ) groups
        """)
        groups = cur.fetchone()[0]

    return {"total_rows": total, "duplicate_groups": groups}


def _build_outbox_row(row: dict) -> tuple:
    """Build the ``outbox_events`` tuple for one row about to be deleted.

    Mirrors ``OutboxRepository._build``: a fresh uuid4 id, the event's own
    ``event_type``/``correlation_id``, and ``status='pending'`` so the
    publisher picks it up.  The routing key is derived from ``event_type``
    by the worker, so nothing else is needed here.

    The event is constructed from the real contract class — if
    ``TransactionDeletedEvent`` ever gains a required field, this raises
    instead of silently emitting a payload consumers cannot parse.
    """
    from contracts.events.transaction import TransactionDeletedEvent

    event = TransactionDeletedEvent(
        transaction_id=row["id"],
        account_id=row["account_id"],
        user_id=row["user_id"],
        amount=str(row["amount"]),
    )
    return (
        str(uuid4()),
        "transaction",
        str(row["id"]),
        event.event_type,
        event.to_json(),
        event.correlation_id,
        "pending",
        0,
    )


def _delete_rows(conn, rows: list[dict]) -> int:
    """Delete rows and outbox their delete events in one transaction.

    Both statements share the cursor and a single commit, so the read model
    can never learn about a delete that did not happen — nor miss one that
    did.  Insert first: a failed DELETE then rolls the events back with it.
    """
    ids = [row["id"] for row in rows]
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO outbox_events (
                id, aggregate_type, aggregate_id, event_type,
                payload_json, correlation_id, status, attempts
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [_build_outbox_row(row) for row in rows],
        )
        outboxed = cur.rowcount

        cur.execute(
            "DELETE FROM transactions WHERE id = ANY(%s)",
            (ids,),
        )
        deleted = cur.rowcount

    if deleted != outboxed:
        conn.rollback()
        raise RuntimeError(
            f"Refusing to commit: {outboxed} delete events for {deleted} deleted rows. "
            "Write model and read model would diverge."
        )

    conn.commit()
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove duplicate transactions from PostgreSQL (transaction-service)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete duplicate rows. Without this flag, only a dry-run report is shown.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  PostgreSQL Transaction Duplicate Cleanup")
    print("=" * 60)
    print()

    conn = _get_connection()
    conn.autocommit = False

    fk_constraints = _check_fk_constraints(conn)
    if fk_constraints:
        logger.warning("FK constraints referencing transactions:")
        for name, table in fk_constraints:
            logger.warning("  %s on %s", name, table)
        logger.warning("DELETE may fail if referencing rows exist. Check these tables first.")
    else:
        logger.info("No FK constraints reference transactions table.")

    summary = _get_summary(conn)
    logger.info("Total transaction rows:   %d", summary["total_rows"])
    logger.info("Duplicate groups:         %d", summary["duplicate_groups"])

    to_delete = _find_duplicates(conn)
    logger.info("Rows to delete:           %d", len(to_delete))

    if not to_delete:
        logger.info("No duplicates found. Database is clean.")
        conn.close()
        return

    print(f"\nSample rows to delete (first 10 of {len(to_delete)}):")
    for row in to_delete[:10]:
        print(f"  id={row['id']}  date={row['date']!s}  amount={row['amount']!s}  "
              f"desc={row['description']!r}  sub_id={row['subcategory_id']}  "
              f"tier={row['categorization_tier']}  "
              f"group_size={row['group_size']}  keeping_id={row['keep_id']}")
    print()

    if not args.execute:
        conn.rollback()
        print("DRY RUN — no rows deleted. Pass --execute to delete.")
        conn.close()
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = BACKUP_DIR / f"pg_deleted_dupes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    with open(audit_path, "w", encoding="utf-8") as f:
        for row in to_delete:
            f.write(json.dumps(row, cls=_Encoder, ensure_ascii=False) + "\n")
    logger.info("Audit log written to %s (%d rows)", audit_path, len(to_delete))

    deleted = _delete_rows(conn, to_delete)
    logger.info("Deleted %d duplicate rows (+ %d delete events outboxed)", deleted, deleted)

    new_summary = _get_summary(conn)
    logger.info("Rows after cleanup:       %d (was %d)", new_summary["total_rows"], summary["total_rows"])

    conn.close()
    print("\nCleanup complete.")


if __name__ == "__main__":
    main()
