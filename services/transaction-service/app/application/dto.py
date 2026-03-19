from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import CategoryType, TransactionType

CATEGORY_NAME_MIN = 1
CATEGORY_NAME_MAX_LEN = 45

AMOUNT_MIN = Decimal("0.01")
AMOUNT_MAX = Decimal("9999999999.99")
DESCRIPTION_MAX = 500
ACCOUNT_NAME_MAX = 100
CATEGORY_NAME_MAX = 100

# Alias to prevent collision when a Pydantic field is also named ``date``
DateType = date


class CreateCategoryDTO(BaseModel):
    name: str = Field(min_length=CATEGORY_NAME_MIN, max_length=CATEGORY_NAME_MAX_LEN)
    type: CategoryType


class UpdateCategoryDTO(BaseModel):
    name: str | None = Field(default=None, min_length=CATEGORY_NAME_MIN, max_length=CATEGORY_NAME_MAX_LEN)
    type: CategoryType | None = None


class CategoryResponseDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: CategoryType


class CreateTransactionDTO(BaseModel):
    account_id: int = Field(gt=0)
    account_name: str = Field(max_length=ACCOUNT_NAME_MAX)
    category_id: int | None = Field(default=None, gt=0)
    category_name: str | None = Field(default=None, max_length=CATEGORY_NAME_MAX)
    amount: Decimal = Field(ge=AMOUNT_MIN, le=AMOUNT_MAX, decimal_places=2)
    transaction_type: TransactionType
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    date: date


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    account_id: int
    account_name: str
    category_id: int | None
    category_name: str | None
    amount: Decimal
    transaction_type: TransactionType
    description: str | None
    date: date
    created_at: datetime


class UpdateTransactionDTO(BaseModel):
    account_id: int | None = Field(default=None, gt=0)
    account_name: str | None = Field(default=None, max_length=ACCOUNT_NAME_MAX)
    category_id: int | None = None
    category_name: str | None = Field(default=None, max_length=CATEGORY_NAME_MAX)
    amount: Decimal | None = Field(default=None, ge=AMOUNT_MIN, le=AMOUNT_MAX, decimal_places=2)
    transaction_type: TransactionType | None = None
    description: str | None = None
    date: DateType | None = None


class TransactionFiltersDTO(BaseModel):
    account_id: int | None = None
    category_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    transaction_type: TransactionType | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class CSVImportResultDTO(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


class CreatePlannedTransactionDTO(BaseModel):
    account_id: int = Field(gt=0)
    account_name: str = Field(max_length=ACCOUNT_NAME_MAX)
    category_id: int | None = Field(default=None, gt=0)
    category_name: str | None = Field(default=None, max_length=CATEGORY_NAME_MAX)
    amount: Decimal = Field(ge=AMOUNT_MIN, le=AMOUNT_MAX, decimal_places=2)
    transaction_type: TransactionType
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    recurrence: str = Field(pattern=r"^(daily|weekly|biweekly|monthly|yearly)$")
    next_execution: date


class UpdatePlannedTransactionDTO(BaseModel):
    amount: Decimal | None = Field(default=None, ge=AMOUNT_MIN, le=AMOUNT_MAX, decimal_places=2)
    description: str | None = None
    recurrence: str | None = Field(
        default=None,
        pattern=r"^(daily|weekly|biweekly|monthly|yearly)$",
    )
    next_execution: date | None = None
    is_active: bool | None = None


class PlannedTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    account_id: int
    account_name: str
    category_id: int | None
    category_name: str | None
    amount: Decimal
    transaction_type: TransactionType
    description: str | None
    recurrence: str
    next_execution: date
    is_active: bool
    created_at: datetime
