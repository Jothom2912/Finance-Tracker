from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.account_adapter import AccountServiceAdapter
from app.adapters.outbound.enable_banking_client import (
    EnableBankingClient,
    EnableBankingConfig,
)
from app.adapters.outbound.unit_of_work import SQLAlchemyUnitOfWork
from app.application.service import BankingService
from app.config import settings
from app.database import get_db

_banking_client: EnableBankingClient | None = None


def _get_banking_client() -> EnableBankingClient:
    global _banking_client
    if _banking_client is None:
        config = EnableBankingConfig(
            app_id=settings.ENABLE_BANKING_APP_ID,
            key_path=settings.ENABLE_BANKING_KEY_PATH,
            redirect_uri=settings.ENABLE_BANKING_REDIRECT_URI,
        )
        _banking_client = EnableBankingClient(config)
    return _banking_client


async def get_banking_service(
    session: AsyncSession = Depends(get_db),
) -> BankingService:
    uow = SQLAlchemyUnitOfWork(session)
    account_port = AccountServiceAdapter(
        base_url=settings.ACCOUNT_SERVICE_URL,
        api_key=settings.INTERNAL_API_KEY,
        timeout=settings.ACCOUNT_SERVICE_TIMEOUT,
    )
    return BankingService(
        uow=uow,
        account_port=account_port,
        banking_client=_get_banking_client(),
    )
