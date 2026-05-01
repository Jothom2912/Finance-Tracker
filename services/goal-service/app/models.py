from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from app.database import Base
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class GoalModel(Base):
    __tablename__ = "goals"

    idGoal: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(45), nullable=True)
    target_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    current_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, server_default="0")
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str | None] = mapped_column(String(45), nullable=True)
    Account_idAccount: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_default_savings_goal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "ix_goals_one_default_per_account",
            "Account_idAccount",
            unique=True,
            postgresql_where=sa.text("is_default_savings_goal = TRUE"),
            sqlite_where=sa.text("is_default_savings_goal = 1"),
        ),
    )


class GoalAllocationHistoryModel(Base):
    __tablename__ = "goal_allocation_history"

    id: Mapped[str] = mapped_column(sa.Uuid(as_uuid=False), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.idGoal"), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(sa.Uuid(as_uuid=False), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_goal_allocation_history_positive_amount"),
        Index("ix_goal_allocation_history_goal_id", "goal_id"),
        Index("ix_goal_allocation_history_source_key", "source_key"),
        sa.UniqueConstraint("source_key", "goal_id", name="uq_goal_allocation_history_source_goal"),
    )


class UnallocatedBudgetSurplusModel(Base):
    __tablename__ = "unallocated_budget_surplus"

    id: Mapped[str] = mapped_column(sa.Uuid(as_uuid=False), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(sa.Uuid(as_uuid=False), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_unallocated_budget_surplus_positive_amount"),
        Index("ix_unallocated_budget_surplus_account_id", "account_id"),
        sa.UniqueConstraint("source_key", name="uq_unallocated_budget_surplus_source_key"),
    )


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (Index("ix_outbox_pending_poll", "status", "next_attempt_at", "created_at"),)
