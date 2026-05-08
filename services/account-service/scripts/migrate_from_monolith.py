"""Data migration: copy accounts from monolith MySQL to account-service PostgreSQL.

Usage:
    DATABASE_URL=postgresql+psycopg2://... \
    MYSQL_URL=mysql+pymysql://root:root@localhost:3307/finans_tracker \
    python -m scripts.migrate_from_monolith [--dry-run]

This script is IDEMPOTENT: it skips rows that already exist in the target DB
(matched by original idAccount). Run it as many times as needed.
"""

import argparse
import logging
import os
import sys

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate accounts from monolith MySQL to account PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be migrated without writing")
    args = parser.parse_args()

    mysql_url = os.environ.get("MYSQL_URL")
    pg_url = os.environ.get("DATABASE_URL")

    if not mysql_url:
        logger.error("MYSQL_URL environment variable is required")
        sys.exit(1)
    if not pg_url:
        logger.error("DATABASE_URL environment variable is required")
        sys.exit(1)

    mysql_engine = create_engine(mysql_url)
    pg_engine = create_engine(pg_url)

    with mysql_engine.connect() as mysql_conn:
        accounts = mysql_conn.execute(
            text("SELECT idAccount, name, saldo, User_idUser, budget_start_day FROM Account")
        ).fetchall()
        logger.info(f"Found {len(accounts)} accounts in monolith MySQL")

        groups = mysql_conn.execute(
            text("SELECT idAccountGroups, name FROM AccountGroups")
        ).fetchall()
        logger.info(f"Found {len(groups)} account groups in monolith MySQL")

        group_users = mysql_conn.execute(
            text("SELECT AccountGroups_idAccountGroups, User_idUser FROM AccountGroups_has_User")
        ).fetchall()
        logger.info(f"Found {len(group_users)} group-user associations in monolith MySQL")

    if args.dry_run:
        logger.info("[DRY RUN] Would migrate:")
        for a in accounts:
            logger.info(f"  Account id={a[0]} name={a[1]} user={a[3]}")
        for g in groups:
            logger.info(f"  Group id={g[0]} name={g[1]}")
        for gu in group_users:
            logger.info(f"  Group-User group={gu[0]} user={gu[1]}")
        return

    with pg_engine.begin() as pg_conn:
        migrated_accounts = 0
        skipped_accounts = 0
        for a in accounts:
            existing = pg_conn.execute(
                text('SELECT 1 FROM "Account" WHERE "idAccount" = :id'),
                {"id": a[0]},
            ).fetchone()
            if existing:
                skipped_accounts += 1
                continue
            pg_conn.execute(
                text(
                    'INSERT INTO "Account" ("idAccount", name, saldo, "User_idUser", budget_start_day) '
                    "VALUES (:id, :name, :saldo, :user_id, :budget_start_day)"
                ),
                {
                    "id": a[0],
                    "name": a[1],
                    "saldo": float(a[2]) if a[2] else 0.0,
                    "user_id": a[3],
                    "budget_start_day": a[4] if a[4] else 1,
                },
            )
            migrated_accounts += 1

        migrated_groups = 0
        skipped_groups = 0
        for g in groups:
            existing = pg_conn.execute(
                text('SELECT 1 FROM "AccountGroups" WHERE "idAccountGroups" = :id'),
                {"id": g[0]},
            ).fetchone()
            if existing:
                skipped_groups += 1
                continue
            pg_conn.execute(
                text(
                    'INSERT INTO "AccountGroups" ("idAccountGroups", name, max_users) '
                    "VALUES (:id, :name, 20)"
                ),
                {"id": g[0], "name": g[1]},
            )
            migrated_groups += 1

        migrated_gu = 0
        for gu in group_users:
            existing = pg_conn.execute(
                text(
                    'SELECT 1 FROM "AccountGroups_has_User" '
                    'WHERE "AccountGroups_idAccountGroups" = :gid AND "User_idUser" = :uid'
                ),
                {"gid": gu[0], "uid": gu[1]},
            ).fetchone()
            if existing:
                continue
            pg_conn.execute(
                text(
                    'INSERT INTO "AccountGroups_has_User" '
                    '("AccountGroups_idAccountGroups", "User_idUser") VALUES (:gid, :uid)'
                ),
                {"gid": gu[0], "uid": gu[1]},
            )
            migrated_gu += 1

        seq_val = pg_conn.execute(
            text('SELECT COALESCE(MAX("idAccount"), 0) + 1 FROM "Account"')
        ).scalar()
        pg_conn.execute(text(f'ALTER SEQUENCE "Account_idAccount_seq" RESTART WITH {seq_val}'))

        seq_val_g = pg_conn.execute(
            text('SELECT COALESCE(MAX("idAccountGroups"), 0) + 1 FROM "AccountGroups"')
        ).scalar()
        pg_conn.execute(text(f'ALTER SEQUENCE "AccountGroups_idAccountGroups_seq" RESTART WITH {seq_val_g}'))

    logger.info(f"Accounts: migrated={migrated_accounts}, skipped={skipped_accounts}")
    logger.info(f"Groups: migrated={migrated_groups}, skipped={skipped_groups}")
    logger.info(f"Group-User associations: migrated={migrated_gu}")
    logger.info("Migration complete!")


if __name__ == "__main__":
    main()
