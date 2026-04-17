"""
MySQL adapter for Merchant repository.
"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.category.application.ports.outbound import IMerchantRepository
from backend.category.domain.entities import Merchant
from backend.models.mysql.merchant import Merchant as MerchantModel


class MySQLMerchantRepository(IMerchantRepository):
    """MySQL implementation of merchant repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self._db = db

    def find_by_normalized_name(self, name: str) -> Optional[Merchant]:
        model = self._db.query(MerchantModel).filter(MerchantModel.normalized_name == name).first()
        return self._to_entity(model) if model else None

    def get_by_id(self, merchant_id: int) -> Optional[Merchant]:
        model = self._db.query(MerchantModel).filter(MerchantModel.id == merchant_id).first()
        return self._to_entity(model) if model else None

    def get_by_subcategory_id(self, subcategory_id: int) -> list[Merchant]:
        models = self._db.query(MerchantModel).filter(MerchantModel.subcategory_id == subcategory_id).all()
        return [self._to_entity(m) for m in models]

    def save(self, merchant: Merchant) -> Merchant:
        existing = (
            self._db.query(MerchantModel).filter(MerchantModel.normalized_name == merchant.normalized_name).first()
        )
        if existing:
            existing.display_name = merchant.display_name
            existing.subcategory_id = merchant.subcategory_id
            existing.transaction_count = merchant.transaction_count
            existing.is_user_confirmed = merchant.is_user_confirmed
            self._db.commit()
            self._db.refresh(existing)
            return self._to_entity(existing)

        model = MerchantModel(
            normalized_name=merchant.normalized_name,
            display_name=merchant.display_name,
            subcategory_id=merchant.subcategory_id,
            transaction_count=merchant.transaction_count,
            is_user_confirmed=merchant.is_user_confirmed,
        )
        self._db.add(model)
        self._db.commit()
        self._db.refresh(model)
        return self._to_entity(model)

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
