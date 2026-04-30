"""Inbound ports for the Categorization bounded context."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.application.dto import (
    CategorizeRequestDTO,
    CategorizeResponseDTO,
    CategoryResponseDTO,
    CreateCategoryDTO,
    SubCategoryResponseDTO,
    UpdateCategoryDTO,
)


class ICategorizationService(ABC):
    """Sync categorization endpoint — tier 1 only."""

    @abstractmethod
    async def categorize(self, request: CategorizeRequestDTO) -> CategorizeResponseDTO: ...

    @abstractmethod
    async def categorize_batch(
        self,
        requests: list[CategorizeRequestDTO],
    ) -> list[CategorizeResponseDTO]: ...


class ICategoryService(ABC):
    """CRUD for taxonomy (categories + subcategories)."""

    @abstractmethod
    async def create_category(self, dto: CreateCategoryDTO) -> CategoryResponseDTO: ...

    @abstractmethod
    async def list_categories(self) -> list[CategoryResponseDTO]: ...

    @abstractmethod
    async def get_category(self, category_id: int) -> CategoryResponseDTO: ...

    @abstractmethod
    async def update_category(self, category_id: int, dto: UpdateCategoryDTO) -> CategoryResponseDTO: ...

    @abstractmethod
    async def delete_category(self, category_id: int) -> None: ...

    @abstractmethod
    async def list_subcategories(self, category_id: int) -> list[SubCategoryResponseDTO]: ...
