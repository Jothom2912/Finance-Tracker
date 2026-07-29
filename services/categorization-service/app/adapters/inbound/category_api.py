"""Taxonomy endpoints — categories and subcategories.

Per ADR-003 (supersedes ADR-002), categorization-service is the sole
owner and writer of the full taxonomy. Write routes emit full-state
``category.*`` / ``subcategory.*`` events via the transactional outbox;
transaction-service maintains event-synced read copies.

Routing layout — reads and writes are separate routers with separate
auth, because the taxonomy is data every user shares (P2-28):

- ``/api/v1/categories`` (JWT): category reads + nested subcategory list
- ``/api/v1/subcategories`` (JWT): flat list-all, for gateway's N+1
- ``/api/v1/internal/…`` (``X-Internal-API-Key``): every write

A user JWT authenticates but does not authorize a taxonomy write: a
rename fans out through ``propagate_category_rename`` to every user's
denormalized ``category_name`` in Elasticsearch, and no "in use" guard
can catch it because nothing is orphaned. See
``dev-notes/decisions/2026-07-29-taxonomy-authorization.md``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.adapters.inbound.internal_auth import require_internal_api_key
from app.application.category_service import CategoryService
from app.application.dto import (
    CategoryResponseDTO,
    CreateCategoryDTO,
    CreateSubCategoryDTO,
    SubCategoryResponseDTO,
    UpdateCategoryDTO,
    UpdateSubCategoryDTO,
)
from app.auth import get_current_user_id
from app.dependencies import get_category_service

category_router = APIRouter(prefix="/api/v1/categories", tags=["categories"])
subcategory_router = APIRouter(prefix="/api/v1/subcategories", tags=["subcategories"])

# Router-level guard, not per-endpoint — same reason as ``categorize_router``:
# a write route added here later is guarded by default rather than by
# remembering to opt in. Router-level is also what makes the decision cheap
# to revisit: swapping in an ``is_admin`` dependency is one line here.
taxonomy_admin_router = APIRouter(
    prefix="/api/v1/internal",
    tags=["taxonomy-admin"],
    dependencies=[Depends(require_internal_api_key)],
)


# ── Categories (read) ──


@category_router.get("/", response_model=list[CategoryResponseDTO])
async def list_categories(
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponseDTO]:
    return await service.list_categories()


@category_router.get("/{category_id}", response_model=CategoryResponseDTO)
async def get_category(
    category_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.get_category(category_id)


# ── Subcategories (nested under parent, read) ──


@category_router.get(
    "/{category_id}/subcategories",
    response_model=list[SubCategoryResponseDTO],
)
async def list_subcategories(
    category_id: int,
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> list[SubCategoryResponseDTO]:
    return await service.list_subcategories(category_id)


# ── Subcategories (flat list, read) ──


@subcategory_router.get("/", response_model=list[SubCategoryResponseDTO])
async def list_all_subcategories(
    _user_id: int = Depends(get_current_user_id),
    service: CategoryService = Depends(get_category_service),
) -> list[SubCategoryResponseDTO]:
    return await service.list_all_subcategories()


# ── Writes (internal-only, P2-28) ──
#
# No ``get_current_user_id`` dependency on any of these: it would resolve an
# identity nothing uses, and leaving it in place would suggest an ownership
# check that does not exist. The taxonomy has no owner but the service.


@taxonomy_admin_router.post(
    "/categories/",
    response_model=CategoryResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(
    dto: CreateCategoryDTO,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.create_category(dto)


@taxonomy_admin_router.put("/categories/{category_id}", response_model=CategoryResponseDTO)
async def update_category(
    category_id: int,
    dto: UpdateCategoryDTO,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponseDTO:
    return await service.update_category(category_id, dto)


@taxonomy_admin_router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    service: CategoryService = Depends(get_category_service),
) -> None:
    await service.delete_category(category_id)


@taxonomy_admin_router.post(
    "/categories/{category_id}/subcategories",
    response_model=SubCategoryResponseDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_subcategory(
    category_id: int,
    dto: CreateSubCategoryDTO,
    service: CategoryService = Depends(get_category_service),
) -> SubCategoryResponseDTO:
    return await service.create_subcategory(category_id, dto)


@taxonomy_admin_router.put("/subcategories/{subcategory_id}", response_model=SubCategoryResponseDTO)
async def update_subcategory(
    subcategory_id: int,
    dto: UpdateSubCategoryDTO,
    service: CategoryService = Depends(get_category_service),
) -> SubCategoryResponseDTO:
    return await service.update_subcategory(subcategory_id, dto)


@taxonomy_admin_router.delete(
    "/subcategories/{subcategory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subcategory(
    subcategory_id: int,
    service: CategoryService = Depends(get_category_service),
) -> None:
    await service.delete_subcategory(subcategory_id)
