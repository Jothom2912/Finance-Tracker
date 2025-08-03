from pydantic import BaseModel, Field
# Import TransactionType fra din database.py fil
from ..database import TransactionType 

class CategoryBase(BaseModel):
    name: str
    type: TransactionType = TransactionType.expense

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: int = Field(..., description="Unique ID of the category.")

    class Config:
        from_attributes = True