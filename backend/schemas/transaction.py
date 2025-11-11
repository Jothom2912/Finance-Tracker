from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

# Import TransactionType fra din database.py fil
# Bemærk den relative import sti her, da den er inde i 'backend' pakken
from ..database import TransactionType 
# Importer Category skemaet, da Transaction skemaet bruger det
from .category import Category # Dette er den Pydantic Category model

class TransactionBase(BaseModel):
    description: Optional[str] = None   
    amount: float
    date: date
    type: TransactionType = TransactionType.expense # Bruger TransactionType enum'en
    category_id: Optional[int] = None # Foreign Key til Category

class TransactionCreate(TransactionBase):
    pass # Arver alle felter fra TransactionBase

class Transaction(TransactionBase):
    id: int = Field(..., description="Unique ID of the transaction.")
    # Inkluder Category skemaet her for at returnere den relaterede kategori data
    # når en transaktion hentes. Dette bruges med SQLAlchemy's joinedload.
    category: Optional[Category] = None 

    class Config:
        # Fortæller Pydantic at den skal mappe felter fra SQLAlchemy ORM-objekter
        # til Pydantic-skemaet. Også kendt som `orm_mode = True` i ældre Pydantic versioner.
        from_attributes = True