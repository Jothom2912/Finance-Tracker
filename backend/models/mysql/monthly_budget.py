"""SQLAlchemy models for the MonthlyBudget aggregate."""

from sqlalchemy import UniqueConstraint

from .common import (
    Base,
    Column,
    Integer,
    DECIMAL,
    DateTime,
    ForeignKey,
    relationship,
    func,
)


class MonthlyBudget(Base):
    """A monthly budget groups all budget lines for one account in one period."""

    __tablename__ = "MonthlyBudget"

    id = Column(Integer, primary_key=True, autoincrement=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    account_id = Column(
        Integer,
        ForeignKey("Account.idAccount", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(DateTime, server_default=func.now())

    account = relationship("Account")
    lines = relationship(
        "BudgetLine",
        back_populates="monthly_budget",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    __table_args__ = (
        UniqueConstraint("account_id", "month", "year", name="uq_account_month_year"),
    )

    def __repr__(self) -> str:
        return f"<MonthlyBudget(id={self.id}, {self.year}-{self.month:02d})>"


class BudgetLine(Base):
    """A single category budget line within a MonthlyBudget."""

    __tablename__ = "BudgetLine"

    id = Column(Integer, primary_key=True, autoincrement=True)
    monthly_budget_id = Column(
        Integer,
        ForeignKey("MonthlyBudget.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id = Column(
        Integer,
        ForeignKey("Category.idCategory"),
        nullable=False,
    )
    amount = Column(DECIMAL(15, 2), nullable=False)

    monthly_budget = relationship("MonthlyBudget", back_populates="lines")
    category = relationship("Category")

    __table_args__ = (
        UniqueConstraint(
            "monthly_budget_id", "category_id", name="uq_budget_category"
        ),
    )

    def __repr__(self) -> str:
        return f"<BudgetLine(id={self.id}, cat={self.category_id}, amount={self.amount})>"
