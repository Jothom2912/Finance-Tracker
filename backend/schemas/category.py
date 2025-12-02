from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from ..validation_boundaries import CATEGORY_BVA

# Forward references for relationships (minimal info)
class TransactionBase(BaseModel):
    idTransaction: int
    amount: float
    type: str
    class Config:
        from_attributes = True

class BudgetBase(BaseModel):
    idBudget: int
    amount: float
    class Config:
        from_attributes = True


# --- Base Schema ---
class CategoryBase(BaseModel):
    name: str = Field(
        ...,
        min_length=CATEGORY_BVA.name_min_length,
        max_length=CATEGORY_BVA.name_max_length,
        description="Category name (1-30 characters)"
    )
    type: str = Field(
        ...,
        description="Category type: 'income' or 'expense'"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=CATEGORY_BVA.description_max_length,
        description="Optional category description (max 200 characters)"
    )

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """BVA: Type må være enten 'income' eller 'expense'"""
        if v not in CATEGORY_BVA.valid_types:
            raise ValueError(f"Type må være en af {CATEGORY_BVA.valid_types}, fik: {v}")
        return v

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """BVA: Navn må ikke være tomt eller kun mellemrum"""
        if not v or v.strip() == "":
            raise ValueError("Navn må ikke være tomt")
        return v.strip()

    @field_validator('description')
    @classmethod
    def validate_description_not_empty(cls, v: Optional[str]) -> Optional[str]:
        """BVA: Hvis beskrivelse exists, må den ikke være kun mellemrum"""
        if v is not None and v.strip() == "":
            return None
        return v


# --- Schema for creation ---
class CategoryCreate(CategoryBase):
    pass

# --- Schema for reading data ---
class Category(CategoryBase):
    idCategory: int
    
    # Relationships
    transactions: List[TransactionBase] = []
    budgets: List[BudgetBase] = []

    class Config:
        from_attributes = True