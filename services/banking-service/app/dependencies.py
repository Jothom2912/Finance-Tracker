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
    # Process-wide singleton: the underlying httpx.AsyncClient keeps a
    # TCP/TLS connection pool that should be shared across requests
    # (per-request clients would re-handshake and re-read the PEM every
    # call). Closed once via aclose_banking_client() in app lifespan.
    global _banking_client
    if _banking_client is None:
        config = EnableBankingConfig(
            app_id=settings.ENABLE_BANKING_APP_ID,
            key_path=settings.ENABLE_BANKING_KEY_PATH,
            redirect_uri=settings.ENABLE_BANKING_REDIRECT_URI,
            max_tx_pages=settings.MAX_TX_PAGES,
        )
        _banking_client = EnableBankingClient(config)
    return _banking_client


async def aclose_banking_client() -> None:
    """Release the shared HTTP connection pool (called on app shutdown)."""
    global _banking_client
    if _banking_client is not None:
        await _banking_client.aclose()
        _banking_client = None


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
