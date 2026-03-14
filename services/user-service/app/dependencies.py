from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.ports.inbound import IUserService
from app.application.service import UserService
from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db


async def get_user_service(
    db: AsyncSession = Depends(get_db),
) -> IUserService:
    uow = SQLAlchemyUnitOfWork(db)
    return UserService(
        uow=uow,
        hash_password=hash_password,
        verify_password=verify_password,
        create_token=create_access_token,
    )
