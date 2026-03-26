"""Outbound ports for Banking bounded context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from backend.banking.adapters.outbound.enable_banking_client import BankTransaction


class IBankConnectionRepository(ABC):
    """Port for bank connection persistence."""

    @abstractmethod
    def get_by_account_id(self, account_id: int) -> list[Any]:
        pass

    @abstractmethod
    def get_by_session_id(self, session_id: str) -> Optional[Any]:
        pass

    @abstractmethod
    def create(self, connection: Any) -> Any:
        pass

    @abstractmethod
    def update_last_synced(self, connection_id: int) -> None:
        pass

    @abstractmethod
    def delete(self, connection_id: int) -> bool:
        pass


class IBankingApiClient(ABC):
    """Port for external banking API (Enable Banking, etc.)."""

    @abstractmethod
    def get_available_banks(self, country: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def start_authorization(
        self, bank_name: str, country: str, valid_days: int
    ) -> dict[str, str]:
        pass

    @abstractmethod
    def create_session(self, auth_code: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def get_transactions(
        self,
        account_uid: str,
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> list[BankTransaction]:
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        pass
