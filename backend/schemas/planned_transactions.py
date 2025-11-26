from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

# Forward references for relationships (minimal info)
class TransactionBase(BaseModel):
    idTransaction: int
    description: Optional[str] = None
    class Config:
        from_attributes = True

# --- Base Schema ---
class PlannedTransactionsBase(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = None

# --- Schema for creation ---
class PlannedTransactionsCreate(PlannedTransactionsBase):
    # Tillader at en planlagt transaktion oprettes uden en allerede eksisterende transaktion
    pass

# --- Schema for reading data (includes relationship) ---
class PlannedTransactions(PlannedTransactionsBase):
    idPlannedTransactions: int
    Transaction_idTransaction: Optional[int] = None
    
    # Relationship
    transaction: Optional[TransactionBase] = None # Kan være NULL

    class Config:
        from_attributes = True
        json_encoders = {
            Decimal: lambda v: float(v),
        }