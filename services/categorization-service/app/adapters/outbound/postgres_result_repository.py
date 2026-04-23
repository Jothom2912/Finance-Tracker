from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ICategorizationResultRepository
from app.domain.entities import CategorizationResultRecord
from app.domain.value_objects import CategorizationTier, Confidence
from app.models import CategorizationResultModel


class PostgresCategorizationResultRepository(ICategorizationResultRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, record: CategorizationResultRecord) -> CategorizationResultRecord:
        model = CategorizationResultModel(
            transaction_id=record.transaction_id,
            category_id=record.category_id,
            subcategory_id=record.subcategory_id,
            merchant_id=record.merchant_id,
            tier=record.tier.value,
            confidence=record.confidence.value,
            model_version=record.model_version,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_transaction_id(
        self,
        transaction_id: int,
    ) -> list[CategorizationResultRecord]:
        stmt = (
            select(CategorizationResultModel)
            .where(CategorizationResultModel.transaction_id == transaction_id)
            .order_by(CategorizationResultModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(model: CategorizationResultModel) -> CategorizationResultRecord:
        return CategorizationResultRecord(
            id=model.id,
            transaction_id=model.transaction_id,
            category_id=model.category_id,
            subcategory_id=model.subcategory_id,
            merchant_id=model.merchant_id,
            tier=CategorizationTier(model.tier),
            confidence=Confidence(model.confidence),
            model_version=model.model_version,
            created_at=model.created_at,
        )
