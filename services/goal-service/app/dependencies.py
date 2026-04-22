from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.account_adapter import UserServiceAccountAdapter
from app.adapters.outbound.postgres_goal_repository import AsyncPostgresGoalRepository
from app.application.ports.inbound import IGoalService
from app.application.service import GoalService
from app.config import settings
from app.database import get_db


async def get_goal_service(
    db: AsyncSession = Depends(get_db),
) -> IGoalService:
    goal_repo = AsyncPostgresGoalRepository(db)
    account_port = UserServiceAccountAdapter(
        base_url=settings.USER_SERVICE_URL,
        timeout=settings.USER_SERVICE_TIMEOUT,
    )
    return GoalService(goal_repository=goal_repo, account_port=account_port)