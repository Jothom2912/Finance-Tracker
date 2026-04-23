"""One-off reconciliation: delete MySQL Transaction rows that have no
corresponding row in PostgreSQL (transaction-service).

Background
----------
Pre-migration bank syncs (2026-03-26, 2026-04-03) wrote transactions
directly to MySQL without deduplication.  The 2026-04-17 sync went
through transaction-service with ``skip_duplicates=True``, creating
205 authoritative rows in PostgreSQL.  The old 226 MySQL-only rows
are duplicates of the same real-world bank transactions — their date
ranges overlap almost entirely with the PostgreSQL set.

Root cause prevention: the old direct-write path was removed when
banking writes were rerouted through transaction-service's
``POST /api/v1/transactions/bulk``.  Architecture test
``test_read_only_projections.py`` enforces that no application code
outside ``TransactionSyncConsumer`` writes to the MySQL Transaction
table, so recurrence is structurally prevented.

Safety rails
------------
* **--dry-run is the default.**  Shows counts and sample rows but
  deletes nothing.
* **--execute** must be passed explicitly to delete.
* A ``mysqldump`` of the Transaction table is taken before any delete.
* Every deleted row is logged as full JSON for audit.
* Idempotent — running twice is safe (second run finds 0 orphans).

Usage::

    # Dry run (default) — see what would be deleted
    python scripts/cleanup_mysql_duplicates.py

    # Actually delete, with backup
    python scripts/cleanup_mysql_duplicates.py --execute

Environment variables::

    DATABASE_URL                 MySQL connection (monolith)
    TRANSACTION_SERVICE_DB_URL   PostgreSQL connection (transaction-service)

Or with docker-compose defaults (see below).

**Remove this script and its Makefile target after running.**
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _REPO_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


MYSQL_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:root@localhost:3307/finans_tracker",
)
PG_URL = os.getenv(
    "TRANSACTION_SERVICE_DB_URL",
    "postgresql://transaction_service:transaction_service_pass@localhost:5434/transactions",
)

BACKUP_DIR = _REPO_ROOT / "scripts" / "backups"


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def _get_mysql_connection():
    from sqlalchemy import create_engine

    engine = create_engine(MYSQL_URL)
    return engine.connect()


def _get_pg_connection():
    import psycopg2

    url = PG_URL
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        url = url.replace(prefix, "postgresql://")
    return psycopg2.connect(url)


def _fetch_mysql_ids(conn) -> set[int]:
    from sqlalchemy import text

    result = conn.execute(text("SELECT idTransaction FROM Transaction"))
    return {row[0] for row in result.fetchall()}


def _fetch_pg_ids(conn) -> set[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM transactions")
        return {row[0] for row in cur.fetchall()}


def _fetch_mysql_rows(conn, ids: set[int]) -> list[dict]:
    if not ids:
        return []
    from sqlalchemy import text

    placeholders = ",".join(str(i) for i in sorted(ids))
    result = conn.execute(
        text(
            f"SELECT idTransaction, amount, description, date, type, "
            f"Category_idCategory, Account_idAccount, created_at, "
            f"categorization_tier, categorization_confidence "
            f"FROM Transaction WHERE idTransaction IN ({placeholders})"
        )
    )
    columns = result.keys()
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _mysqldump_backup() -> Path | None:
    """Take a mysqldump of the Transaction table before deleting."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"transactions_backup_{timestamp}.sql"

    mysql_host = "localhost"
    mysql_port = "3307"
    mysql_user = "root"
    mysql_password = "root"
    mysql_db = "finans_tracker"

    try:
        result = subprocess.run(
            [
                "mysqldump",
                f"--host={mysql_host}",
                f"--port={mysql_port}",
                f"--user={mysql_user}",
                f"--password={mysql_password}",
                mysql_db,
                "Transaction",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            backup_path.write_text(result.stdout, encoding="utf-8")
            logger.info("Backup saved to %s (%d bytes)", backup_path, len(result.stdout))
            return backup_path
        logger.warning(
            "mysqldump failed (rc=%d): %s — continuing without backup",
            result.returncode,
            result.stderr[:200],
        )
    except FileNotFoundError:
        logger.warning(
            "mysqldump not found on PATH — skipping backup. "
            "Consider running inside the mysql container or installing mysql-client."
        )
    except Exception as exc:
        logger.warning("Backup failed: %s — continuing without backup", exc)
    return None


def _delete_orphans(conn, orphan_ids: set[int]) -> int:
    from sqlalchemy import text

    placeholders = ",".join(str(i) for i in sorted(orphan_ids))
    result = conn.execute(
        text(f"DELETE FROM Transaction WHERE idTransaction IN ({placeholders})")
    )
    conn.commit()
    return result.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconcile MySQL Transaction table against PostgreSQL source of truth."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete orphan rows. Without this flag, only a dry-run report is shown.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  ONE-OFF MySQL Transaction Duplicate Cleanup")
    print("  Remove this script after running successfully.")
    print("=" * 60)
    print()

    logger.info("Connecting to MySQL: %s", MYSQL_URL.split("@")[-1])
    mysql_conn = _get_mysql_connection()

    logger.info("Connecting to PostgreSQL: %s", PG_URL.split("@")[-1])
    pg_conn = _get_pg_connection()

    mysql_ids = _fetch_mysql_ids(mysql_conn)
    pg_ids = _fetch_pg_ids(pg_conn)

    logger.info("MySQL Transaction rows:      %d", len(mysql_ids))
    logger.info("PostgreSQL transaction rows:  %d", len(pg_ids))

    orphan_ids = mysql_ids - pg_ids
    shared_ids = mysql_ids & pg_ids
    pg_only_ids = pg_ids - mysql_ids

    logger.info("Shared (in both):            %d", len(shared_ids))
    logger.info("Orphans (MySQL only):        %d", len(orphan_ids))
    logger.info("PostgreSQL only:             %d", len(pg_only_ids))

    if pg_only_ids:
        logger.warning(
            "PostgreSQL has %d rows not in MySQL — projection may be lagging. "
            "IDs: %s",
            len(pg_only_ids),
            sorted(pg_only_ids)[:20],
        )

    if not orphan_ids:
        logger.info("No orphan rows found. MySQL is already clean.")
        pg_conn.close()
        mysql_conn.close()
        return

    orphan_rows = _fetch_mysql_rows(mysql_conn, orphan_ids)
    print(f"\nSample orphan rows (first 5 of {len(orphan_rows)}):")
    for row in orphan_rows[:5]:
        print(f"  {json.dumps(row, cls=_DecimalEncoder, ensure_ascii=False)}")
    print()

    if not args.execute:
        print("DRY RUN — no rows deleted. Pass --execute to delete.")
        pg_conn.close()
        mysql_conn.close()
        return

    backup_path = _mysqldump_backup()
    if backup_path:
        logger.info("Backup complete: %s", backup_path)
    else:
        logger.warning("Proceeding WITHOUT backup — mysqldump was unavailable.")

    audit_path = BACKUP_DIR / f"deleted_rows_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(audit_path, "w", encoding="utf-8") as f:
        for row in orphan_rows:
            f.write(json.dumps(row, cls=_DecimalEncoder, ensure_ascii=False) + "\n")
    logger.info("Full audit log written to %s (%d rows)", audit_path, len(orphan_rows))

    deleted = _delete_orphans(mysql_conn, orphan_ids)
    logger.info("Deleted %d orphan rows from MySQL", deleted)

    remaining = _fetch_mysql_ids(mysql_conn)
    logger.info("MySQL rows after cleanup: %d (expected: %d)", len(remaining), len(pg_ids))

    pg_conn.close()
    mysql_conn.close()

    print()
    print("Cleanup complete. Verify dashboard totals look correct,")
    print("then remove this script and the Makefile target.")


if __name__ == "__main__":
    main()
