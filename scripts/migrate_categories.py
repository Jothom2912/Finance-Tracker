"""One-shot migration: copy categories from monolith MySQL to
transaction-service PostgreSQL.

Preserves original IDs so existing transaction.category_id references
remain valid.  Resets the PostgreSQL sequence after insert.

Usage (from project root)::

    # With default Docker Compose URLs
    python scripts/migrate_categories.py

    # With custom URLs
    python scripts/migrate_categories.py \
        --mysql "mysql+pymysql://root:root@localhost:3306/finans_tracker" \
        --postgres "postgresql://transaction_service:transaction_service_pass@localhost:5433/transactions"
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    text,
)

MYSQL_DEFAULT = "mysql+pymysql://root:root@localhost:3306/finans_tracker"
PG_DEFAULT = "postgresql://transaction_service:transaction_service_pass@localhost:5433/transactions"


def migrate(mysql_url: str, pg_url: str) -> None:
    mysql_engine = create_engine(mysql_url)
    pg_engine = create_engine(pg_url)

    mysql_meta = MetaData()
    mysql_categories = Table(
        "Category",
        mysql_meta,
        Column("idCategory", Integer, primary_key=True),
        Column("name", String(45)),
        Column("type", String(45)),
    )

    with mysql_engine.connect() as conn:
        rows = conn.execute(mysql_categories.select()).fetchall()

    if not rows:
        print("No categories found in MySQL. Nothing to migrate.")
        return

    print(f"Found {len(rows)} categories in MySQL:")
    for row in rows:
        print(f"  id={row.idCategory}  name={row.name!r}  type={row.type}")

    pg_meta = MetaData()
    pg_categories = Table(
        "categories",
        pg_meta,
        Column("id", Integer, primary_key=True),
        Column("name", String(45)),
        Column("type", String(20)),
    )

    with pg_engine.begin() as conn:
        for row in rows:
            existing = conn.execute(
                pg_categories.select().where(pg_categories.c.id == row.idCategory)
            ).first()

            if existing:
                print(f"  SKIP id={row.idCategory} (already exists)")
                continue

            conn.execute(
                pg_categories.insert().values(
                    id=row.idCategory,
                    name=row.name,
                    type=row.type,
                )
            )
            print(f"  INSERT id={row.idCategory} name={row.name!r}")

        max_id = conn.execute(
            text("SELECT COALESCE(MAX(id), 0) FROM categories")
        ).scalar()
        conn.execute(
            text(f"SELECT setval('categories_id_seq', {max_id}, true)")
        )
        print(f"\nPostgreSQL sequence reset to {max_id}")

    print("Migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate categories from monolith MySQL to transaction-service PostgreSQL",
    )
    parser.add_argument(
        "--mysql",
        default=MYSQL_DEFAULT,
        help=f"MySQL connection URL (default: {MYSQL_DEFAULT})",
    )
    parser.add_argument(
        "--postgres",
        default=PG_DEFAULT,
        help=f"PostgreSQL connection URL (default: {PG_DEFAULT})",
    )
    args = parser.parse_args()

    try:
        migrate(args.mysql, args.postgres)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
