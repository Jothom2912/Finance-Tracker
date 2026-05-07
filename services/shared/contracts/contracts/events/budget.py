from __future__ import annotations

from decimal import Decimal, InvalidOperation

from pydantic import Field, field_validator

from contracts.base import BaseEvent


def make_budget_month_closed_source_key(account_id: int, year: int, month: int) -> str:
    return f"budget.month_closed:{account_id}:{year}:{month}"


class BudgetMonthClosedEvent(BaseEvent):
    """Published when an account-level budget month is closed.

    ``surplus_amount`` is calculated as:
    max(0, sum(budgeted_per_account) - sum(actual_spent_per_account)).

    Amount fields are decimal strings to preserve exact money values.
    Consumers parse them with ``Decimal(value)`` before comparing or adding.
    """

    event_type: str = "budget.month_closed"
    event_version: int = 1

    account_id: int = Field(ge=1)
    year: int = Field(ge=2020)
    month: int = Field(ge=1, le=12)
    budgeted_amount: str
    actual_spent: str
    surplus_amount: str

    @field_validator("budgeted_amount", "actual_spent", "surplus_amount")
    @classmethod
    def validate_decimal_string(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except (InvalidOperation, ValueError) as err:
            raise ValueError("amount must be a decimal string") from err

        if amount < 0:
            raise ValueError("amount must be greater than or equal to 0")

        return value

    @property
    def source_key(self) -> str:
        return make_budget_month_closed_source_key(
            account_id=self.account_id,
            year=self.year,
            month=self.month,
        )
