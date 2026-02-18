"""
Inbound ports (driving adapters) for Category bounded context.
Defines the service interface for external consumers.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.category.application.dto import CategoryCreateDTO, CategoryResponseDTO


class ICategoryService(ABC):
    """Inbound port defining category use cases."""

    @abstractmethod
    def get_category(self, category_id: int) -> Optional[CategoryResponseDTO]:
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[CategoryResponseDTO]:
        pass

    @abstractmethod
    def list_categories(
        self, skip: int = 0, limit: int = 100
    ) -> list[CategoryResponseDTO]:
        pass

    @abstractmethod
    def create_category(self, dto: CategoryCreateDTO) -> CategoryResponseDTO:
        pass

    @abstractmethod
    def update_category(
        self, category_id: int, dto: CategoryCreateDTO
    ) -> Optional[CategoryResponseDTO]:
        pass

    @abstractmethod
    def delete_category(self, category_id: int) -> bool:
        pass
