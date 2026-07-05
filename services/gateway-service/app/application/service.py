from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from app.application.dto import (
    CategoryExpense,
    FinancialOverview,
    SubcategoryExpense,
    TransactionProjection,
)
from app.application.ports.outbound import IAnalyticsReadRepository, ICategoryReadRepository

logger = logging.getLogger(__name__)

UNCATEGORIZED_LABEL = "Ukategoriseret"
NO_SUBCATEGORY_LABEL = "(Ingen underkategori)"


class AnalyticsService:
    def __init__(
        self,
        read_repo: IAnalyticsReadRepository,
        category_repo: ICategoryReadRepository | None = None,
    ):
        self._read_repo = read_repo
        self._category_repo = category_repo

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
        )

        category_id_to_name = self._category_name_map()

        total_income = 0.0
        total_expenses = 0.0
        # Aggregation is keyed by ids (None = uncategorized), never names —
        # renamed/duplicate names must not merge buckets.
        category_buckets: dict[int | None, dict] = {}
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
                self._add_expense_to_bucket(
                    category_buckets,
                    transaction,
                    abs(amount),
                    category_id_to_name,
                )
            else:
                current_account_balance += amount

        expenses_by_category = self._buckets_to_expenses(category_buckets)

        net_change_in_period = total_income - total_expenses
        months_in_period = max(
            1,
            (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1,
        )
        if months_in_period == 1:
            days_in_period = (end_date - start_date).days + 1
            months_in_period = max(1, days_in_period / 30.0)

        average_monthly_expenses = total_expenses / months_in_period if months_in_period > 0 else 0.0

        return FinancialOverview(
            start_date=start_date,
            end_date=end_date,
            total_income=round(total_income, 2),
            total_expenses=round(total_expenses, 2),
            net_change_in_period=round(net_change_in_period, 2),
            expenses_by_category=expenses_by_category,
            current_account_balance=round(current_account_balance, 2),
            average_monthly_expenses=round(average_monthly_expenses, 2),
        )

    def _category_name_map(self) -> dict[int, str]:
        if self._category_repo is None:
            return {}
        try:
            categories = self._category_repo.get_categories()
        except Exception:
            # Taxonomy source down: degrade to the denormalized names on
            # the transaction rows rather than failing the whole overview.
            logger.warning("Could not fetch categories from taxonomy source", exc_info=True)
            return {}
        return {cat["id"]: cat["name"] for cat in categories if cat.get("id") is not None}

    @staticmethod
    def _add_expense_to_bucket(
        buckets: dict[int | None, dict],
        transaction: dict,
        amount: float,
        category_id_to_name: dict[int, str],
    ) -> None:
        category_id = transaction.get("category_id")
        bucket = buckets.get(category_id)
        if bucket is None:
            # Display name: authoritative taxonomy first, denormalized row
            # name as fallback (sync lag / deleted category), else the
            # explicit uncategorized label.
            name = (
                category_id_to_name.get(category_id)
                or transaction.get("category_name")
                or UNCATEGORIZED_LABEL
            )
            bucket = {"name": name, "amount": 0.0, "subcategories": {}}
            buckets[category_id] = bucket

        bucket["amount"] += amount

        subcategory_id = transaction.get("subcategory_id")
        sub_bucket = bucket["subcategories"].get(subcategory_id)
        if sub_bucket is None:
            sub_name = (
                transaction.get("subcategory_name") or NO_SUBCATEGORY_LABEL
                if subcategory_id is not None
                else NO_SUBCATEGORY_LABEL
            )
            sub_bucket = {"name": sub_name, "amount": 0.0}
            bucket["subcategories"][subcategory_id] = sub_bucket
        sub_bucket["amount"] += amount

    @staticmethod
    def _buckets_to_expenses(buckets: dict[int | None, dict]) -> list[CategoryExpense]:
        expenses = [
            CategoryExpense(
                category_id=category_id,
                category_name=bucket["name"],
                amount=round(bucket["amount"], 2),
                subcategories=sorted(
                    (
                        SubcategoryExpense(
                            subcategory_id=sub_id,
                            subcategory_name=sub["name"],
                            amount=round(sub["amount"], 2),
                        )
                        for sub_id, sub in bucket["subcategories"].items()
                    ),
                    key=lambda s: s.amount,
                    reverse=True,
                ),
            )
            for category_id, bucket in buckets.items()
        ]
        return sorted(expenses, key=lambda e: e.amount, reverse=True)

    def list_transaction_projections(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[TransactionProjection]:
        if not account_id:
            raise ValueError("Account ID er påkrævet for at hente transaktioner.")

        raw = self._read_repo.get_transactions(
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
        )

        projections: list[TransactionProjection] = []
        for row in raw:
            if category_id is not None and row.get("category_id") != category_id:
                continue
            row_type = self._normalize_tx_type(row.get("type"))
            if tx_type is not None and row_type != tx_type.strip().lower():
                continue

            row_date = self._normalize_date(row.get("date"))
            if row_date is None:
                continue

            projections.append(
                TransactionProjection(
                    id=row.get("id"),
                    amount=float(row.get("amount", 0)),
                    description=row.get("description"),
                    date=row_date,
                    type=row_type,
                    category_id=row.get("category_id"),
                    category_name=row.get("category_name"),
                    subcategory_id=row.get("subcategory_id"),
                    subcategory_name=row.get("subcategory_name"),
                    account_id=row.get("account_id"),
                    categorization_tier=row.get("categorization_tier"),
                )
            )
            if len(projections) >= limit:
                break

        return projections

    def get_expenses_by_month(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        budget_start_day: int = 1,
    ) -> list[dict[str, Any]]:
        from app.shared.budget_period import determine_budget_month

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

            b_year, b_month = determine_budget_month(tx_date, budget_start_day)
            key = f"{b_year}-{b_month:02d}"
            monthly_expenses[key] = monthly_expenses.get(key, 0.0) + abs(amount)

        return [
            {"month": month_key, "total_expenses": round(total, 2)}
            for month_key, total in sorted(monthly_expenses.items())
        ]

    @staticmethod
    def _normalize_date(raw_value: Any) -> Optional[date]:
        if raw_value is None:
            return None
        if isinstance(raw_value, date):
            return raw_value
        if isinstance(raw_value, datetime):
            return raw_value.date()
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
