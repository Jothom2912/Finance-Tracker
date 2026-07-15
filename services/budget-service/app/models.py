from __future__ import annotations

from datetime import date, datetime

from messaging import OutboxEventMixin
from sqlalchemy import Date, ForeignKey, Integer, Numeric, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BudgetModel(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    budget_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())


class MonthlyBudgetModel(Base):
    __tablename__ = "monthly_budgets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    lines: Mapped[list[BudgetLineModel]] = relationship(
        "BudgetLineModel",
        back_populates="monthly_budget",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (UniqueConstraint("account_id", "month", "year", name="uq_monthly_budget_account_period"),)


class BudgetLineModel(Base):
    __tablename__ = "budget_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    monthly_budget_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("monthly_budgets.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    monthly_budget: Mapped[MonthlyBudgetModel] = relationship(back_populates="lines")

    __table_args__ = (UniqueConstraint("monthly_budget_id", "category_id", name="uq_budget_line_budget_category"),)


class OutboxEventModel(OutboxEventMixin, Base):
    """Service-owned outbox table; columns come from the shared mixin.

    Kept as a thin local class so Alembic metadata stays service-owned
    (columns and ``ix_outbox_pending_poll`` match the outbox migration exactly).
    """
