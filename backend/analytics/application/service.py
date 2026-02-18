"""
Application service for Analytics bounded context.
"""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Optional

from backend.analytics.application.ports.outbound import IAnalyticsReadRepository
from backend.shared.schemas.budget import BudgetSummary, BudgetSummaryItem
from backend.shared.schemas.dashboard import FinancialOverview

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Application service for dashboard and budget summary analytics."""

    def __init__(self, read_repo: IAnalyticsReadRepository):
        self._read_repo = read_repo

    def get_financial_overview(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> FinancialOverview:
        if not account_id:
            raise ValueError("Account ID er påkrævet for at hente finansielt overblik.")

        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        if start_date > end_date:
            raise ValueError("Startdato kan ikke være efter slutdato.")

        transactions = self._read_repo.get_transactions(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        categories = self._read_repo.get_categories()
        category_id_to_name = {
            cat.get("idCategory"): cat.get("name")
            for cat in categories
            if cat.get("idCategory")
        }

        total_income = 0.0
        total_expenses = 0.0
        category_expenses: dict[str, float] = {}
        current_account_balance = 0.0

        for transaction in transactions:
            amount = float(transaction.get("amount", 0))
            tx_type = self._normalize_tx_type(transaction.get("type"))
            is_income = tx_type == "income" or (tx_type == "" and amount > 0)
            is_expense = tx_type == "expense" or (tx_type == "" and amount < 0)

            if is_income:
                total_income += abs(amount)
                current_account_balance += abs(amount)
            elif is_expense:
                total_expenses += abs(amount)
                current_account_balance -= abs(amount)
                category_id = transaction.get("Category_idCategory")
                if category_id:
                    category_name = category_id_to_name.get(category_id, "Ukategoriseret")
                    category_expenses[category_name] = (
                        category_expenses.get(category_name, 0.0) + abs(amount)
                    )
            else:
                current_account_balance += amount

        net_change_in_period = total_income - total_expenses
        months_in_period = max(
            1,
            (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1,
        )
        if months_in_period == 1:
            days_in_period = (end_date - start_date).days + 1
            months_in_period = max(1, days_in_period / 30.0)

        average_monthly_expenses = (
            total_expenses / months_in_period if months_in_period > 0 else 0.0
        )

        return FinancialOverview(
            start_date=start_date,
            end_date=end_date,
            total_income=round(total_income, 2),
            total_expenses=round(total_expenses, 2),
            net_change_in_period=round(net_change_in_period, 2),
            expenses_by_category={k: round(v, 2) for k, v in category_expenses.items()},
            current_account_balance=round(current_account_balance, 2),
            average_monthly_expenses=round(average_monthly_expenses, 2),
        )

    def get_expenses_by_month(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = date(end_date.year - 1, end_date.month, 1)
        if start_date > end_date:
            raise ValueError("Startdato kan ikke være efter slutdato.")

        transactions = self._read_repo.get_transactions(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        monthly_expenses: dict[str, float] = {}
        for transaction in transactions:
            amount = float(transaction.get("amount", 0))
            tx_type = self._normalize_tx_type(transaction.get("type"))
            is_expense = tx_type == "expense" or (tx_type == "" and amount < 0)
            if not is_expense:
                continue

            tx_date = self._normalize_date(transaction.get("date"))
            if not tx_date:
                continue

            key = f"{tx_date.year}-{tx_date.month:02d}"
            monthly_expenses[key] = monthly_expenses.get(key, 0.0) + abs(amount)

        return [
            {"month": month_key, "total_expenses": round(total, 2)}
            for month_key, total in sorted(monthly_expenses.items())
        ]

    def get_budget_summary(self, account_id: int, month: int, year: int) -> BudgetSummary:
        budgets = self._read_repo.get_budgets(account_id=account_id)

        filtered_budgets: list[dict] = []
        for budget in budgets:
            budget_date = self._normalize_date(budget.get("budget_date"))
            if budget_date and budget_date.month == month and budget_date.year == year:
                filtered_budgets.append(budget)

        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)

        transactions = self._read_repo.get_transactions(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,
        )

        expenses_by_category: dict[int, float] = {}
        for transaction in transactions:
            amount = float(transaction.get("amount", 0))
            tx_type = self._normalize_tx_type(transaction.get("type"))
            if tx_type == "expense" or (tx_type == "" and amount < 0):
                category_id = transaction.get("Category_idCategory")
                if category_id:
                    expenses_by_category[category_id] = (
                        expenses_by_category.get(category_id, 0.0) + abs(amount)
                    )

        categories = self._read_repo.get_categories()
        category_id_to_name = {
            cat.get("idCategory"): cat.get("name", "Ukendt")
            for cat in categories
            if cat.get("idCategory")
        }

        items: list[BudgetSummaryItem] = []
        total_budget = 0.0
        total_spent = 0.0
        over_budget_count = 0
        budget_category_ids: set[int] = set()

        for budget in filtered_budgets:
            category_id = budget.get("Category_idCategory")
            if not category_id:
                continue

            budget_amount = float(budget.get("amount") or 0.0)
            spent = expenses_by_category.get(category_id, 0.0)
            remaining = budget_amount - spent
            percentage_used = (spent / budget_amount * 100.0) if budget_amount > 0 else 0.0

            if remaining < 0:
                over_budget_count += 1

            items.append(
                BudgetSummaryItem(
                    category_id=category_id,
                    category_name=category_id_to_name.get(category_id, "Ukendt"),
                    budget_amount=round(budget_amount, 2),
                    spent_amount=round(spent, 2),
                    remaining_amount=round(remaining, 2),
                    percentage_used=round(percentage_used, 2),
                )
            )
            total_budget += budget_amount
            total_spent += spent
            budget_category_ids.add(category_id)

        missing_budget_category_ids = set(expenses_by_category) - budget_category_ids
        for category_id in missing_budget_category_ids:
            spent = expenses_by_category.get(category_id, 0.0)
            items.append(
                BudgetSummaryItem(
                    category_id=category_id,
                    category_name=category_id_to_name.get(category_id, "Ukendt"),
                    budget_amount=0.0,
                    spent_amount=round(spent, 2),
                    remaining_amount=round(-spent, 2),
                    percentage_used=100.0,
                )
            )
            total_spent += spent

        return BudgetSummary(
            month=f"{month:02d}",
            year=str(year),
            items=items,
            total_budget=round(total_budget, 2),
            total_spent=round(total_spent, 2),
            total_remaining=round(total_budget - total_spent, 2),
            over_budget_count=over_budget_count,
        )

    @staticmethod
    def _normalize_date(raw_value: Any) -> Optional[date]:
        if raw_value is None:
            return None
        if isinstance(raw_value, date):
            return raw_value
        if isinstance(raw_value, datetime):
            return raw_value.date()
        if hasattr(raw_value, "to_native"):
            try:
                native = raw_value.to_native()
                if isinstance(native, datetime):
                    return native.date()
                if isinstance(native, date):
                    return native
            except Exception:
                return None
        if isinstance(raw_value, str):
            try:
                return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).date()
            except ValueError:
                try:
                    return datetime.strptime(raw_value, "%Y-%m-%d").date()
                except ValueError:
                    return None
        return None

    @staticmethod
    def _normalize_tx_type(raw_value: Any) -> str:
        if raw_value is None:
            return ""
        if hasattr(raw_value, "value"):
            return str(raw_value.value).lower()
        return str(raw_value).lower()
