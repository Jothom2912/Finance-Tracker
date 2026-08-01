from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _insert_goal(connection, goal_id: int, status: str | None) -> None:
    connection.execute(
        text(
            """
            INSERT INTO goals (
                idGoal, name, target_amount, current_amount,
                status, Account_idAccount, is_default_savings_goal
            ) VALUES (
                :goal_id, :name, 1000.00, 0.00,
                :status, 42, false
            )
            """
        ),
        {"goal_id": goal_id, "name": f"Goal {goal_id}", "status": status},
    )


def test_migration_006_repairs_and_constrains_stored_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database_path = tmp_path / "goal_006.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    config = _alembic_config(database_url)
    command.upgrade(config, "005")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        for goal_id, status in enumerate((None, "bogus", "completed", "expired", "active", "paused"), start=1):
            _insert_goal(connection, goal_id, status)
    engine.dispose()

    command.upgrade(config, "006")

    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            statuses = connection.execute(text("SELECT idGoal, status FROM goals ORDER BY idGoal")).all()
        assert statuses == [
            (1, "active"),
            (2, "active"),
            (3, "active"),
            (4, "active"),
            (5, "active"),
            (6, "paused"),
        ]

        columns = {column["name"]: column for column in inspect(engine).get_columns("goals")}
        assert columns["status"]["nullable"] is False
        constraints = {constraint["name"] for constraint in inspect(engine).get_check_constraints("goals")}
        assert "ck_goals_status_stored" in constraints

        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                _insert_goal(connection, 7, "bogus")
    finally:
        engine.dispose()

    command.downgrade(config, "005")
    engine = create_engine(database_url)
    try:
        columns = {column["name"]: column for column in inspect(engine).get_columns("goals")}
        assert columns["status"]["nullable"] is True
        constraints = {constraint["name"] for constraint in inspect(engine).get_check_constraints("goals")}
        assert "ck_goals_status_stored" not in constraints
        with engine.begin() as connection:
            _insert_goal(connection, 8, "bogus")
    finally:
        engine.dispose()

    command.upgrade(config, "006")
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT status FROM goals WHERE idGoal = 8")).scalar_one() == "active"
    finally:
        engine.dispose()
