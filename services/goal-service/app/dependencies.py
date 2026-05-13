from __future__ import annotations

from app.adapters.outbound.account_adapter import AccountServiceAdapter
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.ports.inbound import IGoalService
from app.application.service import GoalService
from app.config import settings
from app.database import get_db
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def get_goal_service(db: AsyncSession = Depends(get_db)) -> IGoalService:
    uow = SQLAlchemyUnitOfWork(db)
    account_port = AccountServiceAdapter(
        base_url=settings.ACCOUNT_SERVICE_URL,
        api_key=settings.INTERNAL_API_KEY,
        timeout=settings.ACCOUNT_SERVICE_TIMEOUT,
    )
    return GoalService(uow=uow, account_port=account_port)
