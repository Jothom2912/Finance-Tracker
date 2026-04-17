"""Inbound port for the Category bounded context.

Read-only: write operations were extracted into ``transaction-service``
in milestone 2.  The monolith reads the MySQL projection populated
by ``CategorySyncConsumer``.
"""

from abc import ABC, abstractmethod
from typing import Optional

from backend.category.application.dto import CategoryResponseDTO


class ICategoryService(ABC):
    """Read-only query interface over the Category projection."""

    @abstractmethod
    def get_category(self, category_id: int) -> Optional[CategoryResponseDTO]:
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[CategoryResponseDTO]:
        pass

    @abstractmethod
    def list_categories(self, skip: int = 0, limit: int = 100) -> list[CategoryResponseDTO]:
        pass
