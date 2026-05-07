from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture()
def migrated_engine(tmp_path: Path) -> Engine:
    database_url = f"sqlite:///{tmp_path / 'goal_migrations.db'}"
    command.upgrade(_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


def _insert_goal(
    engine: Engine,
    *,
    goal_id: int,
    account_id: int,
    is_default: bool,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO goals (
                    idGoal,
                    name,
                    target_amount,
                    current_amount,
                    Account_idAccount,
                    is_default_savings_goal
                )
                VALUES (
                    :goal_id,
                    :name,
                    :target_amount,
                    :current_amount,
                    :account_id,
                    :is_default
                )
                """
            ),
            {
                "goal_id": goal_id,
                "name": f"Goal {goal_id}",
                "target_amount": "1000.00",
                "current_amount": "0.00",
                "account_id": account_id,
                "is_default": is_default,
            },
        )


def test_default_goal_unique_index_allows_one_default_per_account(migrated_engine: Engine) -> None:
    _insert_goal(migrated_engine, goal_id=1, account_id=42, is_default=True)
    _insert_goal(migrated_engine, goal_id=2, account_id=42, is_default=False)

    with pytest.raises(IntegrityError):
        _insert_goal(migrated_engine, goal_id=3, account_id=42, is_default=True)

    _insert_goal(migrated_engine, goal_id=4, account_id=43, is_default=True)


@pytest.mark.parametrize("amount", ["0.00", "-1.00"])
def test_goal_allocation_history_rejects_non_positive_amounts(
    migrated_engine: Engine,
    amount: str,
) -> None:
    _insert_goal(migrated_engine, goal_id=10, account_id=42, is_default=True)

    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO goal_allocation_history (
                        id,
                        source_key,
                        goal_id,
                        account_id,
                        amount
                    )
                    VALUES (
                        :id,
                        :source_key,
                        :goal_id,
                        :account_id,
                        :amount
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "source_key": f"budget.month_closed:42:2026:4:{amount}",
                    "goal_id": 10,
                    "account_id": 42,
                    "amount": amount,
                },
            )


@pytest.mark.parametrize("amount", ["0.00", "-1.00"])
def test_unallocated_budget_surplus_rejects_non_positive_amounts(
    migrated_engine: Engine,
    amount: str,
) -> None:
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO unallocated_budget_surplus (
                        id,
                        source_key,
                        account_id,
                        amount,
                        reason
                    )
                    VALUES (
                        :id,
                        :source_key,
                        :account_id,
                        :amount,
                        :reason
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "source_key": f"budget.month_closed:42:2026:4:{amount}",
                    "account_id": 42,
                    "amount": amount,
                    "reason": "no_default_goal",
                },
            )


def test_downgrade_to_002_removes_adr_0003_schema(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'goal_downgrade.db'}"
    config = _alembic_config(database_url)

    command.upgrade(config, "head")
    command.downgrade(config, "002")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)

        assert "goal_allocation_history" not in inspector.get_table_names()
        assert "unallocated_budget_surplus" not in inspector.get_table_names()

        goal_columns = {column["name"] for column in inspector.get_columns("goals")}
        goal_indexes = {index["name"] for index in inspector.get_indexes("goals")}

        assert "is_default_savings_goal" not in goal_columns
        assert "ix_goals_one_default_per_account" not in goal_indexes
    finally:
        engine.dispose()
