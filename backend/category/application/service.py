"""
Application service for Category bounded context.
Orchestrates use cases using domain entities and ports.
"""
from typing import Optional

from backend.category.application.dto import CategoryCreateDTO, CategoryResponseDTO
from backend.category.application.ports.inbound import ICategoryService
from backend.category.application.ports.outbound import ICategoryRepository
from backend.category.domain.entities import Category
from backend.category.domain.exceptions import (
    DuplicateCategoryName,
    DuplicateCategoryNameOnUpdate,
)


class CategoryService(ICategoryService):
    """
    Application service implementing category use cases.

    Uses constructor injection for repository dependency.
    """

    def __init__(self, category_repo: ICategoryRepository):
        self._category_repo = category_repo

    # ------------------------------------------------------------------
    # Query use cases
    # ------------------------------------------------------------------

    def get_category(self, category_id: int) -> Optional[CategoryResponseDTO]:
        """Get a single category by ID."""
        category = self._category_repo.get_by_id(category_id)
        if not category:
            return None
        return self._to_dto(category)

    def get_by_name(self, name: str) -> Optional[CategoryResponseDTO]:
        """Get a category by name."""
        category = self._category_repo.get_by_name(name)
        if not category:
            return None
        return self._to_dto(category)

    def list_categories(
        self, skip: int = 0, limit: int = 100
    ) -> list[CategoryResponseDTO]:
        """List categories with pagination."""
        all_categories = self._category_repo.get_all()
        return [
            self._to_dto(c) for c in all_categories[skip : skip + limit]
        ]

    # ------------------------------------------------------------------
    # Command use cases
    # ------------------------------------------------------------------

    def create_category(self, dto: CategoryCreateDTO) -> CategoryResponseDTO:
        """Create a new category. Raises if name already exists."""
        if self._category_repo.get_by_name(dto.name):
            raise DuplicateCategoryName(dto.name)

        category = Category(
            id=None,
            name=dto.name,
            type=dto.type,
        )

        created = self._category_repo.create(category)
        return self._to_dto(created)

    def update_category(
        self, category_id: int, dto: CategoryCreateDTO
    ) -> Optional[CategoryResponseDTO]:
        """Update an existing category. Raises if new name conflicts."""
        existing = self._category_repo.get_by_id(category_id)
        if not existing:
            return None

        # Check for duplicate name (only if name changed)
        if dto.name != existing.name:
            if self._category_repo.get_by_name(dto.name):
                raise DuplicateCategoryNameOnUpdate(dto.name)

        updated = Category(
            id=category_id,
            name=dto.name,
            type=dto.type,
        )

        result = self._category_repo.update(updated)
        return self._to_dto(result)

    def delete_category(self, category_id: int) -> bool:
        """Delete a category."""
        return self._category_repo.delete(category_id)

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dto(category: Category) -> CategoryResponseDTO:
        return CategoryResponseDTO(
            idCategory=category.id,
            name=category.name,
            type=(
                category.type.value
                if hasattr(category.type, "value")
                else category.type
            ),
        )
