from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.category_port import CategoryPort
from app.adapters.outbound.postgres_budget_repository import PostgresBudgetRepository
from app.application.ports.inbound import IBudgetService
from app.application.service import BudgetService
from app.database import get_db


async def get_budget_service(db: AsyncSession = Depends(get_db)) -> IBudgetService:
    repo = PostgresBudgetRepository(db)
    category_port = CategoryPort()
    return BudgetService(repo=repo, category_port=category_port)
