from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from app.config import settings
from app.database import Base
from app.models import UserModel  # noqa: F401 — registers metadata
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False er ikke kosmetik: default True sætter
    # ``.disabled = True`` på hver logger der findes når migrationen kører — også
    # uvicorns.  Kører alembic i samme proces som appen (migrate-on-startup, som
    # account-service gør), er processen stum bagefter: målt til 4 logliner på 35
    # timers uptime, uden access-log, mens containeren var healthy.  Se P3-58.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
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
