"""Read-only query service for the Category bounded context.

Category write ownership was extracted into ``transaction-service``
(see ``services/transaction-service/app/application/category_service.py``).
This service only exposes queries against the MySQL projection
populated by :class:`backend.consumers.category_sync.CategorySyncConsumer`.

If you need to create, update or delete a category, call
``transaction-service`` over HTTP (or the public REST API at
``:8002/api/v1/categories``).  Attempting to mutate via the
monolith would create a split-brain with the owning service —
forbidden by ``tests/architecture/test_read_only_projections.py``.
"""

from typing import Optional

from backend.category.application.dto import CategoryResponseDTO
from backend.category.application.ports.inbound import ICategoryService
from backend.category.application.ports.outbound import ICategoryRepository
from backend.category.domain.entities import Category


class CategoryService(ICategoryService):
    """Read-only query service over the Category projection."""

    def __init__(self, category_repo: ICategoryRepository):
        self._category_repo = category_repo

    def get_category(self, category_id: int) -> Optional[CategoryResponseDTO]:
        category = self._category_repo.get_by_id(category_id)
        if not category:
            return None
        return self._to_dto(category)

    def get_by_name(self, name: str) -> Optional[CategoryResponseDTO]:
        category = self._category_repo.get_by_name(name)
        if not category:
            return None
        return self._to_dto(category)

    def list_categories(self, skip: int = 0, limit: int = 100) -> list[CategoryResponseDTO]:
        all_categories = self._category_repo.get_all()
        return [self._to_dto(c) for c in all_categories[skip : skip + limit]]

    @staticmethod
    def _to_dto(category: Category) -> CategoryResponseDTO:
        return CategoryResponseDTO(
            idCategory=category.id,
            name=category.name,
            type=(category.type.value if hasattr(category.type, "value") else category.type),
        )
