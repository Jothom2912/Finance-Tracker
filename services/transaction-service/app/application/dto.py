from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.entities import TransactionType

CATEGORY_NAME_MIN = 1
CATEGORY_NAME_MAX_LEN = 45

AMOUNT_MIN = Decimal("0.01")
AMOUNT_MAX = Decimal("9999999999.99")
DESCRIPTION_MAX = 500
ACCOUNT_NAME_MAX = 100
CATEGORY_NAME_MAX = 100
CATEGORIZATION_TIER_MAX = 20
CATEGORIZATION_CONFIDENCE_MAX = 10

# Alias to prevent collision when a Pydantic field is also named ``date``
DateType = date


class CreateTransactionDTO(BaseModel):
    account_id: int = Field(gt=0)
    account_name: str = Field(max_length=ACCOUNT_NAME_MAX)
    category_id: int | None = Field(default=None, gt=0)
    category_name: str | None = Field(default=None, max_length=CATEGORY_NAME_MAX)
    amount: Decimal = Field(ge=AMOUNT_MIN, le=AMOUNT_MAX, decimal_places=2)
    transaction_type: TransactionType
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    date: date
    subcategory_id: int | None = Field(default=None, gt=0)
    categorization_tier: str | None = Field(default=None, max_length=CATEGORIZATION_TIER_MAX)
    categorization_confidence: str | None = Field(
        default=None,
        max_length=CATEGORIZATION_CONFIDENCE_MAX,
    )


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
    subcategory_id: int | None = None
    subcategory_name: str | None = None
    categorization_tier: str | None = None
    categorization_confidence: str | None = None
    external_id: str | None = None
    currency: str = "DKK"


class UpdateTransactionDTO(BaseModel):
    account_id: int | None = Field(default=None, gt=0)
    account_name: str | None = Field(default=None, max_length=ACCOUNT_NAME_MAX)
    category_id: int | None = None
    category_name: str | None = Field(default=None, max_length=CATEGORY_NAME_MAX)
    # exclude_unset semantics: omitted = untouched, explicit null = clear.
    # subcategory_name is deliberately NOT accepted — it is resolved
    # server-side from the local subcategories read copy.
    subcategory_id: int | None = None
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
    duplicates_skipped: int = 0
    errors: list[str]


class BulkCreateTransactionItemDTO(BaseModel):
    """Single transaction in a bulk-create request.

    Extends :class:`CreateTransactionDTO`'s field set with the
    source-system identity for idempotent imports (P2-09):
    ``external_id`` is Enable Banking's ``entry_reference`` — None for
    producers without a stable id (CSV, manual bulk).
    """

    account_id: int = Field(gt=0)
    account_name: str = Field(max_length=ACCOUNT_NAME_MAX)
    category_id: int | None = Field(default=None, gt=0)
    category_name: str | None = Field(default=None, max_length=CATEGORY_NAME_MAX)
    amount: Decimal = Field(ge=AMOUNT_MIN, le=AMOUNT_MAX, decimal_places=2)
    transaction_type: TransactionType
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    date: date
    subcategory_id: int | None = Field(default=None, gt=0)
    categorization_tier: str | None = Field(default=None, max_length=CATEGORIZATION_TIER_MAX)
    categorization_confidence: str | None = Field(
        default=None,
        max_length=CATEGORIZATION_CONFIDENCE_MAX,
    )
    external_id: str | None = Field(default=None, max_length=128)
    currency: str = Field(default="DKK", min_length=3, max_length=3)


class BulkCreateTransactionDTO(BaseModel):
    """Bulk transaction-import request used by trusted internal
    producers such as banking-service.
    """

    items: list[BulkCreateTransactionItemDTO] = Field(min_length=1, max_length=500)
    skip_duplicates: bool = Field(
        default=True,
        description=(
            "If true, duplicates are skipped rather than re-created: "
            "items carrying an external_id dedupe on "
            "(account_id, external_id) — falling back to the fuzzy key "
            "(account_id, date, amount, description) against rows "
            "without an external_id — while items without one use the "
            "fuzzy key alone. With skip_duplicates=false, re-sending an "
            "already-imported external_id fails on the unique index by "
            "design."
        ),
    )


class BulkCreateResultDTO(BaseModel):
    """Outcome of a bulk-import operation."""

    imported: int
    duplicates_skipped: int
    errors: int
    imported_ids: list[int] = Field(default_factory=list)


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
