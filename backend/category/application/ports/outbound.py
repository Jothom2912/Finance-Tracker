"""
Outbound ports (driven adapters) for Category bounded context.
Defines interfaces for infrastructure dependencies.
"""
from abc import ABC, abstractmethod
from typing import Optional

from backend.category.domain.entities import Category


class ICategoryRepository(ABC):
    """Port for category persistence."""

    @abstractmethod
    def get_by_id(self, category_id: int) -> Optional[Category]:
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[Category]:
        pass

    @abstractmethod
    def get_all(self) -> list[Category]:
        pass

    @abstractmethod
    def create(self, category: Category) -> Category:
        pass

    @abstractmethod
    def update(self, category: Category) -> Category:
        pass

    @abstractmethod
    def delete(self, category_id: int) -> bool:
        pass
