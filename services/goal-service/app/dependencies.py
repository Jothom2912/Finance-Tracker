from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.account_adapter import MockAccountAdapter
from app.adapters.outbound.postgres_goal_repository import AsyncPostgresGoalRepository
from app.application.ports.inbound import IGoalService
from app.application.service import GoalService
from app.database import get_db


async def get_goal_service(
    db: AsyncSession = Depends(get_db),
) -> IGoalService:
    goal_repo = AsyncPostgresGoalRepository(db)
    account_port = MockAccountAdapter()
    return GoalService(goal_repository=goal_repo, account_port=account_port)