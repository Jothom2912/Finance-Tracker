from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.ports.outbound import IUnitOfWork
from app.database import get_db


async def get_uow(db: AsyncSession = Depends(get_db)) -> IUnitOfWork:
    return SQLAlchemyUnitOfWork(db)
