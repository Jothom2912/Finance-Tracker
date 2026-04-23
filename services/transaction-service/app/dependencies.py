from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.categorization_client import CategorizationClient
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.category_service import CategoryService
from app.application.ports.inbound import ICategoryService, ITransactionService
from app.application.service import TransactionService
from app.database import get_db

_categorization_client = CategorizationClient()


async def get_transaction_service(
    db: AsyncSession = Depends(get_db),
) -> ITransactionService:
    uow = SQLAlchemyUnitOfWork(db)
    return TransactionService(uow=uow, categorization_client=_categorization_client)


async def get_category_service(
    db: AsyncSession = Depends(get_db),
) -> ICategoryService:
    uow = SQLAlchemyUnitOfWork(db)
    return CategoryService(uow=uow)
