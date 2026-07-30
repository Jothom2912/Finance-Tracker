"""Alembic environment configuration for account-service."""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base  # noqa: E402
from app.models import account, account_groups  # noqa: E402, F401
from app.models.common import account_group_user_association  # noqa: E402, F401

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False er ikke kosmetik: default True sætter
    # ``.disabled = True`` på hver logger der findes når migrationen kører — også
    # uvicorns.  Kører alembic i samme proces som appen (migrate-on-startup, som
    # account-service gør), er processen stum bagefter: målt til 4 logliner på 35
    # timers uptime, uden access-log, mens containeren var healthy.  Se P3-58.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
