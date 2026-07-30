from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from app.database import Base
from app.models.accounts_projection import AccountsProjectionModel  # noqa: F401
from app.models.bank_connection import BankConnectionModel  # noqa: F401
from app.models.outbox import OutboxEventModel  # noqa: F401
from app.models.pending_authorization import PendingAuthorizationModel  # noqa: F401
from app.models.processed_events import ProcessedEventModel  # noqa: F401
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False er ikke kosmetik: default True sætter
    # ``.disabled = True`` på hver logger der findes når migrationen kører — også
    # uvicorns.  Kører alembic i samme proces som appen (migrate-on-startup, som
    # account-service gør), er processen stum bagefter: målt til 4 logliner på 35
    # timers uptime, uden access-log, mens containeren var healthy.  Se P3-58.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

_raw_url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
sync_url = _raw_url.replace("postgresql+asyncpg://", "postgresql://")
config.set_main_option("sqlalchemy.url", sync_url)

target_metadata = Base.metadata


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
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
