from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional


class IAnalyticsReadRepository(ABC):
    @abstractmethod
    def get_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        pass

    @abstractmethod
    def get_categories(self) -> list[dict]:
        pass
