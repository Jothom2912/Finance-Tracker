from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IMerchantRepository
from app.domain.entities import Merchant
from app.models import MerchantModel


class PostgresMerchantRepository(IMerchantRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, merchant: Merchant) -> Merchant:
        if merchant.id is None:
            model = MerchantModel(
                normalized_name=merchant.normalized_name,
                display_name=merchant.display_name,
                subcategory_id=merchant.subcategory_id,
                transaction_count=merchant.transaction_count,
                is_user_confirmed=merchant.is_user_confirmed,
            )
            self._session.add(model)
        else:
            model = await self._session.get(MerchantModel, merchant.id)
            if model is None:
                msg = f"Merchant {merchant.id} not found"
                raise ValueError(msg)
            model.normalized_name = merchant.normalized_name
            model.display_name = merchant.display_name
            model.subcategory_id = merchant.subcategory_id
            model.transaction_count = merchant.transaction_count
            model.is_user_confirmed = merchant.is_user_confirmed

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_id(self, merchant_id: int) -> Optional[Merchant]:
        model = await self._session.get(MerchantModel, merchant_id)
        return self._to_entity(model) if model else None

    async def find_by_normalized_name(self, name: str) -> Optional[Merchant]:
        stmt = select(MerchantModel).where(MerchantModel.normalized_name == name)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_by_subcategory_id(self, subcategory_id: int) -> list[Merchant]:
        stmt = select(MerchantModel).where(MerchantModel.subcategory_id == subcategory_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    @staticmethod
    def _to_entity(model: MerchantModel) -> Merchant:
        return Merchant(
            id=model.id,
            normalized_name=model.normalized_name,
            display_name=model.display_name,
            subcategory_id=model.subcategory_id,
            transaction_count=model.transaction_count,
            is_user_confirmed=model.is_user_confirmed,
        )
