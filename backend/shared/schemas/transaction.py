from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, date
from typing import Optional
from decimal import Decimal
import enum
from backend.validation_boundaries import TRANSACTION_BVA

# --- ENUM for Type (Bruges til validering) ---
class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"

# --- Schema for indlejrede relationer (minimal info) ---
class CategoryBase(BaseModel):
    idCategory: int
    name: str
    model_config = ConfigDict(from_attributes=True)

class AccountBase(BaseModel):
    idAccount: int
    name: str
    model_config = ConfigDict(from_attributes=True)

# --- 1. Base Schema ---
class TransactionBase(BaseModel):
    """Fælles felter for oprettelse og læsning"""
    amount: float = Field(
        ...,
        description="Transaction amount. Must NOT be 0. Can be positive (income) or negative (expense)."
    )
    description: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional transaction description"
    )
    transaction_date: Optional[date] = Field(
        default=None,
        description="Transaction date (defaults to today if not provided)"
    )
    
    # Validering af typen (sikrer at den er 'income' eller 'expense')
    type: TransactionType 
    
    @field_validator('amount')
    @classmethod
    def validate_amount_not_zero(cls, v: float) -> float:
        """BVA: Amount må IKKE være 0
        
        Grænseværdier:
        - -0.01 (gyldig, ekspense)
        - 0 (UGYLDIG)
        - 0.01 (gyldig, indkomst)
        """
        if v == 0 or abs(v) < 0.001:  # Håndter floating point
            raise ValueError("Transaction amount cannot be zero (0)")
        return round(v, 2)

    @field_validator('transaction_date')
    @classmethod
    def validate_transaction_date(cls, v: Optional[date]) -> Optional[date]:
        """BVA: Transaction date skal være valid dato
        
        Typisk accept: historiske + dagens dato
        (Ikke fremtid med mindre det er planlagte transaktioner)
        """
        if v is not None and v > date.today():
            raise ValueError(
                f"Transaction date cannot be in the future. Got: {v}, Today: {date.today()}"
            )
        return v
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v),
        }
    )

# --- 2. Schema for Oprettelse (Bruges i POST) ---
class TransactionCreate(TransactionBase):
    """Felter nødvendige for at oprette en ny transaktion"""
    Category_idCategory: int = Field(..., alias="category_id")
    Account_idAccount: Optional[int] = Field(None, alias="account_id")  # Optional - backend tilføjer det automatisk fra header


# --- 3. Schema for Læsning (Bruges i GET responses) ---
class Transaction(TransactionBase):
    """Fuldt skema, inklusiv ID og relationer"""
    idTransaction: int
    
    Category_idCategory: int
    Account_idAccount: int
    
    # Relationsdata (valgfri i output, hvis de ikke er indlæst)
    category: Optional[CategoryBase] = None
    account: Optional[AccountBase] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            Decimal: lambda v: float(v),
        }
    )

# NB: Hvis du bruger din Transaction model til at læse data, 
# er det Transaction-skemaet, du skal importere i din router.
# (som du gjorde: from backend.schemas.transaction import Transaction as TransactionSchema)