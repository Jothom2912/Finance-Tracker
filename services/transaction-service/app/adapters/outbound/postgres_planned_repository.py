from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IPlannedTransactionRepository
from app.domain.entities import PlannedTransaction, TransactionType
from app.domain.exceptions import PlannedTransactionNotFoundException
from app.models import PlannedTransactionModel


class PostgresPlannedTransactionRepository(IPlannedTransactionRepository):
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
        recurrence: str,
        next_execution: date,
    ) -> PlannedTransaction:
        model = PlannedTransactionModel(
            user_id=user_id,
            account_id=account_id,
            account_name=account_name,
            category_id=category_id,
            category_name=category_name,
            amount=amount,
            transaction_type=transaction_type.value,
            description=description,
            recurrence=recurrence,
            next_execution=next_execution,
            is_active=True,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_id(self, planned_id: int, user_id: int) -> PlannedTransaction | None:
        stmt = select(PlannedTransactionModel).where(
            PlannedTransactionModel.id == planned_id,
            PlannedTransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_user(self, user_id: int) -> list[PlannedTransaction]:
        stmt = (
            select(PlannedTransactionModel)
            .where(PlannedTransactionModel.user_id == user_id)
            .order_by(PlannedTransactionModel.next_execution)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_active(self, user_id: int) -> list[PlannedTransaction]:
        stmt = (
            select(PlannedTransactionModel)
            .where(
                PlannedTransactionModel.user_id == user_id,
                PlannedTransactionModel.is_active.is_(True),
            )
            .order_by(PlannedTransactionModel.next_execution)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, planned_id: int, user_id: int, **fields: object) -> PlannedTransaction:
        stmt = select(PlannedTransactionModel).where(
            PlannedTransactionModel.id == planned_id,
            PlannedTransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            raise PlannedTransactionNotFoundException(planned_id)

        for key, value in fields.items():
            if value is not None and hasattr(model, key):
                setattr(model, key, value)

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def deactivate(self, planned_id: int, user_id: int) -> bool:
        stmt = select(PlannedTransactionModel).where(
            PlannedTransactionModel.id == planned_id,
            PlannedTransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        model.is_active = False
        await self._session.flush()
        return True

    @staticmethod
    def _to_entity(model: PlannedTransactionModel) -> PlannedTransaction:
        return PlannedTransaction(
            id=model.id,
            user_id=model.user_id,
            account_id=model.account_id,
            account_name=model.account_name,
            category_id=model.category_id,
            category_name=model.category_name,
            amount=model.amount,
            transaction_type=TransactionType(model.transaction_type),
            description=model.description,
            recurrence=model.recurrence,
            next_execution=model.next_execution,
            is_active=model.is_active,
            created_at=model.created_at,
        )
