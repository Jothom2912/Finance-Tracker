from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from decimal import Decimal
import enum

# --- ENUM for Type (Bruges til validering) ---
# Genbruger TransactionType fra dit models/common.py
class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"

# --- Schema for indlejrede relationer (minimal info) ---
class CategoryBase(BaseModel):
    idCategory: int
    name: str
    class Config:
        from_attributes = True

class AccountBase(BaseModel):
    idAccount: int
    name: str
    class Config:
        from_attributes = True

# --- 1. Base Schema ---
class TransactionBase(BaseModel):
    """Fælles felter for oprettelse og læsning"""
    amount: Decimal = Field(..., gt=0, decimal_places=2) # Beløbet skal være større end 0
    description: Optional[str] = Field(None, max_length=255)
    date: Optional[datetime] = None # Valgfri, da databasen sætter default til func.now()
    
    # Validering af typen (sikrer at den er 'income' eller 'expense')
    type: TransactionType 
    
    class Config:
        from_attributes = True
        # Konfigurerer Pydantic til at håndtere Decimal (hvis det er nødvendigt for FastAPI)
        json_encoders = {
            Decimal: lambda v: float(v),
        }

# --- 2. Schema for Oprettelse (Bruges i POST) ---
class TransactionCreate(TransactionBase):
    """Felter nødvendige for at oprette en ny transaktion"""
    # Kræver ID'er for de relaterede tabeller
    Category_idCategory: int = Field(..., alias="category_id")
    Account_idAccount: int = Field(..., alias="account_id")


# --- 3. Schema for Læsning (Bruges i GET responses) ---
class Transaction(TransactionBase):
    """Fuldt skema, inklusiv ID og relationer"""
    idTransaction: int
    
    Category_idCategory: int
    Account_idAccount: int
    
    # Relationsdata (valgfri i output, hvis de ikke er indlæst)
    category: Optional[CategoryBase] = None
    account: Optional[AccountBase] = None

# NB: Hvis du bruger din Transaction model til at læse data, 
# er det Transaction-skemaet, du skal importere i din router.
# (som du gjorde: from backend.schemas.transaction import Transaction as TransactionSchema)