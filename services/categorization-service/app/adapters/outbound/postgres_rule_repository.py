from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import IRuleRepository
from app.domain.entities import CategorizationRule
from app.domain.value_objects import PatternType
from app.models import CategorizationRuleModel


class PostgresRuleRepository(IRuleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_active_rules(self, user_id: int | None = None) -> list[CategorizationRule]:
        stmt = select(CategorizationRuleModel).where(
            CategorizationRuleModel.active.is_(True),
        )
        if user_id is not None:
            stmt = stmt.where(
                (CategorizationRuleModel.user_id == user_id) | (CategorizationRuleModel.user_id.is_(None)),
            )
        else:
            stmt = stmt.where(CategorizationRuleModel.user_id.is_(None))

        stmt = stmt.order_by(
            CategorizationRuleModel.priority,
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def create(self, rule: CategorizationRule) -> CategorizationRule:
        model = CategorizationRuleModel(
            user_id=rule.user_id,
            priority=rule.priority,
            pattern_type=rule.pattern_type.value,
            pattern_value=rule.pattern_value,
            matches_subcategory_id=rule.matches_subcategory_id,
            active=rule.active,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def update(self, rule_id: int, **fields: object) -> CategorizationRule:
        stmt = select(CategorizationRuleModel).where(CategorizationRuleModel.id == rule_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            msg = f"Rule {rule_id} not found"
            raise ValueError(msg)

        for key, value in fields.items():
            if key == "pattern_type" and isinstance(value, PatternType):
                value = value.value
            setattr(model, key, value)

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, rule_id: int) -> bool:
        stmt = select(CategorizationRuleModel).where(CategorizationRuleModel.id == rule_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    @staticmethod
    def _to_entity(model: CategorizationRuleModel) -> CategorizationRule:
        return CategorizationRule(
            id=model.id,
            user_id=model.user_id,
            priority=model.priority,
            pattern_type=PatternType(model.pattern_type),
            pattern_value=model.pattern_value,
            matches_subcategory_id=model.matches_subcategory_id,
            active=model.active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
