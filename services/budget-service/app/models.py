from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BudgetModel(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    budget_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(onupdate=func.now())
