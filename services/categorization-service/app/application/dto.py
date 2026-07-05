"""Data Transfer Objects for the Categorization bounded context."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CategorizeRequestDTO(BaseModel):
    """Input for sync /categorize endpoint."""

    transaction_id: int | None = None
    description: str
    amount: float
    user_id: int | None = None


class CategorizeResponseDTO(BaseModel):
    """Output from sync /categorize endpoint."""

    category_id: int
    subcategory_id: int
    merchant_id: int | None = None
    tier: str
    confidence: str
    needs_review: bool = False


class CreateCategoryDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=45)
    type: str = Field(..., description="income, expense, or transfer")
    display_order: int = Field(default=0, ge=0)


class UpdateCategoryDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=45)
    type: str | None = None
    display_order: int | None = Field(default=None, ge=0)


class CreateSubCategoryDTO(BaseModel):
    """category_id comes from the URL path, not the body."""

    name: str = Field(..., min_length=1, max_length=100)


class UpdateSubCategoryDTO(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    category_id: int | None = Field(default=None, gt=0, description="Re-parent to another category")


class CategoryResponseDTO(BaseModel):
    id: int
    name: str
    type: str
    display_order: int = 0


class SubCategoryResponseDTO(BaseModel):
    id: int
    name: str
    category_id: int
    is_default: bool = True
