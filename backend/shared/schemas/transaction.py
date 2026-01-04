from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import datetime, date as date_type
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
    date: date_type = Field(
        default_factory=date_type.today,
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

    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, v):
        """Parser date fra string, datetime eller date objekt. Returnerer date_type.today() hvis None."""
        if v is None:
            return date_type.today()  # Default hvis None
        if isinstance(v, date_type):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            try:
                # Prøv ISO format først
                return datetime.fromisoformat(v.replace('Z', '+00:00')).date()
            except:
                try:
                    # Prøv dansk format (dd-mm-yyyy)
                    return datetime.strptime(v, '%d-%m-%Y').date()
                except:
                    try:
                        # Prøv standard format (yyyy-mm-dd)
                        return datetime.strptime(v, '%Y-%m-%d').date()
                    except:
                        raise ValueError(f"Invalid date format: {v}")
        return v
    
    @field_validator('date')
    @classmethod
    def validate_date(cls, v: date_type) -> date_type:
        """BVA: Transaction date skal være valid dato
        
        Typisk accept: historiske + dagens dato
        (Ikke fremtid med mindre det er planlagte transaktioner)
        """
        if v > date_type.today():
            raise ValueError(
                f"Transaction date cannot be in the future. Got: {v}, Today: {date_type.today()}"
            )
        return v
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            Decimal: lambda v: float(v) if v else 0.0,
            date_type: lambda v: v.isoformat() if v else None,
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
    
    # Timestamp for når transaktionen blev oprettet (auto-genereret)
    created_at: Optional[datetime] = Field(
        None,
        description="Timestamp for when the transaction was created (auto-generated)"
    )
    
    # Relationsdata (valgfri i output, hvis de ikke er indlæst)
    category: Optional[CategoryBase] = None
    account: Optional[AccountBase] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={
            Decimal: lambda v: float(v) if v else 0.0,
            date_type: lambda v: v.isoformat() if v else None,
            datetime: lambda v: v.isoformat() if v else None,
        }
    )

# NB: Hvis du bruger din Transaction model til at læse data, 
# er det Transaction-skemaet, du skal importere i din router.
# (som du gjorde: from backend.schemas.transaction import Transaction as TransactionSchema)