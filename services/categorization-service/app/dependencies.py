"""Dependency injection wiring for categorization-service."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.categorization_service import CategorizationService
from app.application.category_service import CategoryService
from app.database import get_db


async def get_categorization_service(
    db: AsyncSession = Depends(get_db),
) -> CategorizationService:
    """Wire CategorizationService using the startup-warmed provider."""
    from app.main import rule_engine_provider

    engine = await rule_engine_provider.get()

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
