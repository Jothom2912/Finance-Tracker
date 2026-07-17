"""Dependency injection wiring for categorization-service."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.categorization_service import CategorizationService
from app.application.category_service import CategoryService
from app.application.rule_service import RuleService
from app.database import get_db
from app.rule_engine_provider import rule_engine_provider


async def build_categorization_service(user_id: int | None = None) -> CategorizationService:
    """Wire CategorizationService using the startup-warmed provider.

    Built per request/message rather than via Depends: the user scope
    lives in the request BODY (S2S endpoint) or event payload, which
    DI can't see.  With user_id the engine layers the user's own rules
    on top of the global engine (F1-02).
    """
    engine = await rule_engine_provider.get(user_id=user_id)

    return CategorizationService(
        rule_engine=engine,
        fallback_subcategory_id=rule_engine_provider.fallback_subcategory_id,
        fallback_category_id=rule_engine_provider.fallback_category_id,
    )


async def get_category_service(
    db: AsyncSession = Depends(get_db),
) -> CategoryService:
    uow = SQLAlchemyUnitOfWork(db)
    return CategoryService(uow=uow)


async def get_rule_service(
    db: AsyncSession = Depends(get_db),
) -> RuleService:
    """Rule mutations invalidate the in-process user-engine overlay so
    they apply instantly on the API path; worker processes converge via
    the provider TTL."""
    uow = SQLAlchemyUnitOfWork(db)
    return RuleService(uow=uow, on_rules_changed=rule_engine_provider.invalidate_user)
