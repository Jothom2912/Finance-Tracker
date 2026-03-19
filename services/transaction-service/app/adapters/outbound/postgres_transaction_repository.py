from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ITransactionRepository
from app.domain.entities import Transaction, TransactionType
from app.models import TransactionModel


class PostgresTransactionRepository(ITransactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        account_id: int,
        account_name: str,
        category_id: int | None,
        category_name: str | None,
        amount: Decimal,
        transaction_type: TransactionType,
        description: str | None,
        tx_date: date,
    ) -> Transaction:
        model = TransactionModel(
            user_id=user_id,
            account_id=account_id,
            account_name=account_name,
            category_id=category_id,
            category_name=category_name,
            amount=amount,
            transaction_type=transaction_type.value,
            description=description,
            date=tx_date,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_id(self, transaction_id: int, user_id: int) -> Transaction | None:
        stmt = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_user(self, user_id: int, skip: int = 0, limit: int = 50) -> list[Transaction]:
        stmt = (
            select(TransactionModel)
            .where(TransactionModel.user_id == user_id)
            .order_by(TransactionModel.date.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_account(self, account_id: int, user_id: int) -> list[Transaction]:
        stmt = (
            select(TransactionModel)
            .where(
                TransactionModel.account_id == account_id,
                TransactionModel.user_id == user_id,
            )
            .order_by(TransactionModel.date.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_category(self, category_id: int, user_id: int) -> list[Transaction]:
        stmt = (
            select(TransactionModel)
            .where(
                TransactionModel.category_id == category_id,
                TransactionModel.user_id == user_id,
            )
            .order_by(TransactionModel.date.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_date_range(self, user_id: int, start: date, end: date) -> list[Transaction]:
        stmt = (
            select(TransactionModel)
            .where(
                TransactionModel.user_id == user_id,
                TransactionModel.date >= start,
                TransactionModel.date <= end,
            )
            .order_by(TransactionModel.date.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, transaction_id: int, user_id: int, **fields: object) -> Transaction:
        stmt = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            from app.domain.exceptions import TransactionNotFoundException

            raise TransactionNotFoundException(transaction_id)

        for key, value in fields.items():
            if key == "transaction_type" and value is not None:
                value = value.value if isinstance(value, TransactionType) else value
            setattr(model, key, value)

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, transaction_id: int, user_id: int) -> bool:
        stmt = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def bulk_create(self, transactions: list[dict]) -> list[Transaction]:
        models = []
        for tx in transactions:
            tx_type = tx.get("transaction_type", "expense")
            if isinstance(tx_type, TransactionType):
                tx_type = tx_type.value
            models.append(
                TransactionModel(
                    user_id=tx["user_id"],
                    account_id=tx["account_id"],
                    account_name=tx["account_name"],
                    category_id=tx.get("category_id"),
                    category_name=tx.get("category_name"),
                    amount=tx["amount"],
                    transaction_type=tx_type,
                    description=tx.get("description"),
                    date=tx["tx_date"],
                )
            )
        self._session.add_all(models)
        await self._session.flush()
        for m in models:
            await self._session.refresh(m)
        return [self._to_entity(m) for m in models]

    @staticmethod
    def _to_entity(model: TransactionModel) -> Transaction:
        return Transaction(
            id=model.id,
            user_id=model.user_id,
            account_id=model.account_id,
            account_name=model.account_name,
            category_id=model.category_id,
            category_name=model.category_name,
            amount=model.amount,
            transaction_type=TransactionType(model.transaction_type),
            description=model.description,
            date=model.date,
            created_at=model.created_at,
        )
