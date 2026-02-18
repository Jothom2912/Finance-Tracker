"""
Application service for Transaction bounded context.
Orchestrates use cases using domain entities and ports.
"""
import io
import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd

from backend.models.mysql.common import TransactionType
from backend.services.categorization import assign_category_automatically

from backend.transaction.application.dto import (
    PlannedTransactionCreateDTO,
    PlannedTransactionResponseDTO,
    PlannedTransactionUpdateDTO,
    TransactionCreateDTO,
    TransactionResponseDTO,
)
from backend.transaction.application.ports.inbound import ITransactionService
from backend.transaction.application.ports.outbound import (
    ICategoryPort,
    IPlannedTransactionRepository,
    ITransactionRepository,
)
from backend.transaction.domain.entities import PlannedTransaction, Transaction
from backend.transaction.domain.exceptions import (
    AccountRequired,
    CategoryNotFound,
    PlannedTransactionRepositoryNotConfigured,
)

logger = logging.getLogger(__name__)


class TransactionService(ITransactionService):
    """
    Application service implementing transaction use cases.

    Uses constructor injection for all repository dependencies.
    """

    def __init__(
        self,
        transaction_repo: ITransactionRepository,
        category_port: ICategoryPort,
        planned_transaction_repo: Optional[IPlannedTransactionRepository] = None,
    ):
        self._transaction_repo = transaction_repo
        self._category_port = category_port
        self._planned_transaction_repo = planned_transaction_repo

    # ------------------------------------------------------------------
    # Query use cases
    # ------------------------------------------------------------------

    def get_transaction(
        self, transaction_id: int
    ) -> Optional[TransactionResponseDTO]:
        entity = self._transaction_repo.get_by_id(transaction_id)
        if not entity:
            return None
        return self._to_dto(entity)

    def list_transactions(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[int] = None,
        tx_type: Optional[str] = None,
        month: Optional[str] = None,
        year: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[TransactionResponseDTO]:
        if account_id is None:
            raise AccountRequired()

        entities = self._transaction_repo.get_all(
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            account_id=account_id,
            limit=limit,
            offset=skip,
        )

        # Filter by type if specified
        if tx_type:
            normalized_type = tx_type.strip().lower()
            entities = [e for e in entities if e.type == normalized_type]

        # Filter by month/year if specified
        if month is not None or year is not None:
            entities = self._filter_by_month_year(entities, month, year)

        return [self._to_dto(e) for e in entities]

    # ------------------------------------------------------------------
    # Command use cases
    # ------------------------------------------------------------------

    def create_transaction(
        self, dto: TransactionCreateDTO
    ) -> TransactionResponseDTO:
        logger.debug("create_transaction: input = %s", dto.model_dump())

        # Validate category exists
        category = self._category_port.get_by_id(dto.Category_idCategory)
        if not category:
            raise CategoryNotFound(dto.Category_idCategory)
        logger.debug("create_transaction: Kategori fundet: %s", category.name)

        if not dto.Account_idAccount:
            raise AccountRequired()

        tx_type = dto.type
        if hasattr(tx_type, "value"):
            tx_type = tx_type.value

        entity = Transaction(
            id=None,
            amount=dto.amount,
            description=dto.description,
            date=dto.date or date.today(),
            type=tx_type,
            category_id=dto.Category_idCategory,
            account_id=dto.Account_idAccount,
            created_at=datetime.now(),
        )

        created = self._transaction_repo.create(entity)
        logger.debug("create_transaction: Oprettet med ID: %s", created.id)
        return self._to_dto(created)

    def update_transaction(
        self, transaction_id: int, dto: TransactionCreateDTO
    ) -> Optional[TransactionResponseDTO]:
        existing = self._transaction_repo.get_by_id(transaction_id)
        if not existing:
            return None

        # Validate category if changed
        if existing.category_id != dto.Category_idCategory:
            category = self._category_port.get_by_id(dto.Category_idCategory)
            if not category:
                raise CategoryNotFound(dto.Category_idCategory)

        tx_type = dto.type
        if hasattr(tx_type, "value"):
            tx_type = tx_type.value

        updated = Transaction(
            id=transaction_id,
            amount=dto.amount,
            description=dto.description,
            date=dto.date or existing.date,
            type=tx_type,
            category_id=dto.Category_idCategory,
            account_id=dto.Account_idAccount or existing.account_id,
            created_at=existing.created_at,
        )

        result = self._transaction_repo.update(updated)
        if not result:
            return None
        return self._to_dto(result)

    def delete_transaction(self, transaction_id: int) -> bool:
        return self._transaction_repo.delete(transaction_id)

    # ------------------------------------------------------------------
    # Planned Transactions
    # ------------------------------------------------------------------

    def get_planned_transaction(
        self, pt_id: int
    ) -> Optional[PlannedTransactionResponseDTO]:
        if not self._planned_transaction_repo:
            raise PlannedTransactionRepositoryNotConfigured()
        entity = self._planned_transaction_repo.get_by_id(pt_id)
        if not entity:
            return None
        return self._to_planned_dto(entity)

    def list_planned_transactions(
        self, skip: int = 0, limit: int = 100
    ) -> list[PlannedTransactionResponseDTO]:
        if not self._planned_transaction_repo:
            raise PlannedTransactionRepositoryNotConfigured()
        entities = self._planned_transaction_repo.get_all(skip=skip, limit=limit)
        return [self._to_planned_dto(e) for e in entities]

    def create_planned_transaction(
        self, dto: PlannedTransactionCreateDTO
    ) -> PlannedTransactionResponseDTO:
        if not self._planned_transaction_repo:
            raise PlannedTransactionRepositoryNotConfigured()

        entity = PlannedTransaction(
            id=None,
            name=dto.name,
            amount=dto.amount,
        )

        created = self._planned_transaction_repo.create(entity)
        return self._to_planned_dto(created)

    def update_planned_transaction(
        self, pt_id: int, dto: PlannedTransactionUpdateDTO
    ) -> Optional[PlannedTransactionResponseDTO]:
        if not self._planned_transaction_repo:
            raise PlannedTransactionRepositoryNotConfigured()

        existing = self._planned_transaction_repo.get_by_id(pt_id)
        if not existing:
            return None

        update_data = dto.model_dump(exclude_unset=True)

        updated = PlannedTransaction(
            id=pt_id,
            name=update_data.get("name", existing.name),
            amount=update_data.get("amount", existing.amount),
            transaction_id=existing.transaction_id,
        )

        result = self._planned_transaction_repo.update(updated)
        if not result:
            return None
        return self._to_planned_dto(result)

    # ------------------------------------------------------------------
    # CSV Import
    # ------------------------------------------------------------------

    def import_from_csv(
        self, file_contents: bytes, account_id: int
    ) -> list[TransactionResponseDTO]:
        csv_file = io.StringIO(file_contents.decode("utf-8"))

        df = pd.read_csv(
            csv_file, sep=";", decimal=",", thousands=".", dtype={"Beløb": str}
        )

        df = self._parse_csv_dates(df)
        df = df.dropna(subset=["date"])

        if df.empty:
            raise ValueError(
                "Ingen gyldige transaktioner fundet i CSV efter date parsing"
            )

        df["date"] = df["date"].dt.date

        # Parse amount
        df["amount"] = (
            df["Beløb"]
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .astype(float)
        )

        # Get categories and build name->id lookup
        categories = self._category_port.get_all()
        category_name_to_id: dict[str, int] = {
            cat.name.lower(): cat.id
            for cat in categories
            if cat.name
        }

        # Create "Anden" category if missing
        if "anden" not in category_name_to_id:
            try:
                default_cat = self._category_port.create(
                    name="Anden",
                    category_type=TransactionType.expense.value,
                )
                category_name_to_id["anden"] = default_cat.id
            except Exception as e:
                raise ValueError(
                    f"Kunne ikke oprette standardkategorien 'Anden': {e!s}"
                )

        created_transactions: list[TransactionResponseDTO] = []

        try:
            for idx, row in df.iterrows():
                try:
                    amount = float(row["amount"])

                    # Build description
                    parts = [
                        str(row.get("Modtager", "")),
                        str(row.get("Afsender", "")),
                        str(row.get("Navn", "")),
                        str(row.get("Beskrivelse", "")),
                    ]
                    cleaned_parts = [
                        p for p in parts if p and p.lower() != "nan" and p.strip()
                    ]
                    full_description = " ".join(cleaned_parts).strip()
                    if not full_description:
                        full_description = "Ukendt beskrivelse"

                    # Auto-assign category
                    transaction_category_id = assign_category_automatically(
                        transaction_description=full_description,
                        amount=amount,
                        category_name_to_id=category_name_to_id,
                    )

                    tx_type = (
                        TransactionType.income.value
                        if amount >= 0
                        else TransactionType.expense.value
                    )

                    entity = Transaction(
                        id=None,
                        amount=abs(amount),
                        description=full_description,
                        date=row["date"],
                        type=tx_type,
                        category_id=transaction_category_id,
                        account_id=account_id,
                        created_at=datetime.now(),
                    )

                    created = self._transaction_repo.create(entity)
                    created_transactions.append(self._to_dto(created))

                except Exception as row_error:
                    logger.warning(
                        "Fejl ved import af række %s: %s", idx, row_error
                    )
                    continue

            if not created_transactions:
                raise ValueError("Ingen transaktioner kunne importeres fra CSV")

            logger.info(
                "Succesfuldt importeret %s transaktioner til account_id=%s",
                len(created_transactions),
                account_id,
            )
            return created_transactions

        except pd.errors.EmptyDataError:
            raise ValueError("CSV filen er tom")
        except KeyError as e:
            raise ValueError(f"Fejl i CSV format - manglende kolonne: {e}")
        except ValueError:
            raise
        except Exception as e:
            logger.error("Fejl ved import: %s", str(e))
            raise ValueError(f"Fejl ved import af transaktioner: {e!s}")

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dto(entity: Transaction) -> TransactionResponseDTO:
        return TransactionResponseDTO(
            idTransaction=entity.id,
            amount=entity.amount,
            description=entity.description,
            date=entity.date,
            type=entity.type,
            Category_idCategory=entity.category_id,
            Account_idAccount=entity.account_id,
            created_at=entity.created_at,
        )

    @staticmethod
    def _to_planned_dto(entity: PlannedTransaction) -> PlannedTransactionResponseDTO:
        return PlannedTransactionResponseDTO(
            idPlannedTransactions=entity.id,
            name=entity.name,
            amount=entity.amount,
            Transaction_idTransaction=entity.transaction_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _filter_by_month_year(
        entities: list[Transaction],
        month: Optional[str],
        year: Optional[str],
    ) -> list[Transaction]:
        filtered = []
        for e in entities:
            if e.date:
                if month is not None and e.date.month != int(month):
                    continue
                if year is not None and e.date.year != int(year):
                    continue
                filtered.append(e)
        return filtered

    @staticmethod
    def _parse_csv_dates(df: "pd.DataFrame") -> "pd.DataFrame":
        """Parse date column from CSV with different formats."""
        if "Bogføringsdato" in df.columns:
            df["date"] = pd.to_datetime(
                df["Bogføringsdato"], errors="coerce", format="%d-%m-%Y"
            )
            if df["date"].isna().all():
                df["date"] = pd.to_datetime(
                    df["Bogføringsdato"], errors="coerce", format="%d/%m/%Y"
                )
            if df["date"].isna().all():
                df["date"] = pd.to_datetime(
                    df["Bogføringsdato"], errors="coerce", format="%Y/%m/%d"
                )
            if df["date"].isna().all():
                df["date"] = pd.to_datetime(df["Bogføringsdato"], errors="coerce")
        elif "Dato" in df.columns:
            df["date"] = pd.to_datetime(
                df["Dato"], errors="coerce", format="%d-%m-%Y"
            )
            if df["date"].isna().all():
                df["date"] = pd.to_datetime(df["Dato"], errors="coerce")
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        else:
            raise ValueError(
                "CSV mangler 'Bogføringsdato', 'Dato' eller 'date' kolonne"
            )
        return df
