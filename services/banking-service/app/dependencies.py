from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.outbound.enable_banking_client import (
    EnableBankingClient,
    EnableBankingConfig,
)
from app.adapters.outbound.postgres_account_projection_repository import (
    PostgresAccountProjectionRepository,
)
from app.adapters.outbound.postgres_bank_connection_repository import (
    PostgresBankConnectionRepository,
)
from app.adapters.outbound.postgres_pending_auth_repository import (
    PostgresPendingAuthRepository,
)
from app.adapters.outbound.transaction_service_client import TransactionServiceClient
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
    return BankingService(
        bank_connection_repo=PostgresBankConnectionRepository(session),
        pending_auth_repo=PostgresPendingAuthRepository(session),
        account_projection=PostgresAccountProjectionRepository(session),
        banking_client=_get_banking_client(),
        transaction_importer=TransactionServiceClient(),
    )
