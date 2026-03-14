from __future__ import annotations

import csv
import io
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from contracts.events.transaction import (
    TransactionCreatedEvent,
    TransactionDeletedEvent,
)

from app.application.dto import (
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    CSVImportResultDTO,
    PlannedTransactionResponse,
    TransactionFiltersDTO,
    TransactionResponse,
    UpdatePlannedTransactionDTO,
)
from app.application.ports.inbound import ITransactionService
from app.application.ports.outbound import IUnitOfWork
from app.domain.entities import Transaction, TransactionType
from app.domain.exceptions import (
    CSVImportException,
    PlannedTransactionNotFoundException,
    TransactionNotFoundException,
)

logger = logging.getLogger(__name__)

_CSV_REQUIRED_COLUMNS = {
    "date",
    "amount",
    "transaction_type",
    "account_id",
    "account_name",
}


class TransactionService(ITransactionService):
    """Application service for financial transactions.

    Uses a Unit of Work that exposes transaction/planned repos and
    a transactional outbox.  Domain writes and event-intent rows
    are committed atomically — the outbox publisher worker handles
    delivery to RabbitMQ independently.
    """

    def __init__(self, uow: IUnitOfWork) -> None:
        self._uow = uow

    # ── Transactions ────────────────────────────────────────────────

    async def create_transaction(
        self, user_id: int, dto: CreateTransactionDTO
    ) -> TransactionResponse:
        async with self._uow:
            transaction = await self._uow.transactions.create(
                user_id=user_id,
                account_id=dto.account_id,
                account_name=dto.account_name,
                category_id=dto.category_id,
                category_name=dto.category_name,
                amount=dto.amount,
                transaction_type=dto.transaction_type,
                description=dto.description,
                tx_date=dto.date,
            )

            await self._uow.outbox.add(
                event=TransactionCreatedEvent(
                    transaction_id=transaction.id,
                    account_id=transaction.account_id,
                    user_id=user_id,
                    amount=str(transaction.amount),
                    category=transaction.category_name or "",
                    description=transaction.description or "",
                ),
                aggregate_type="transaction",
                aggregate_id=str(transaction.id),
            )

            await self._uow.commit()

        return self._to_response(transaction)

    async def get_transaction(
        self, transaction_id: int, user_id: int
    ) -> TransactionResponse:
        transaction = await self._uow.transactions.find_by_id(
            transaction_id, user_id
        )
        if transaction is None:
            raise TransactionNotFoundException(transaction_id)
        return self._to_response(transaction)

    async def list_transactions(
        self, user_id: int, filters: TransactionFiltersDTO
    ) -> list[TransactionResponse]:
        if filters.account_id is not None:
            results = await self._uow.transactions.find_by_account(
                filters.account_id, user_id
            )
        elif filters.category_id is not None:
            results = await self._uow.transactions.find_by_category(
                filters.category_id, user_id
            )
        elif (
            filters.start_date is not None and filters.end_date is not None
        ):
            results = await self._uow.transactions.find_by_date_range(
                user_id, filters.start_date, filters.end_date
            )
        else:
            results = await self._uow.transactions.find_by_user(
                user_id, skip=filters.skip, limit=filters.limit
            )

        if filters.transaction_type is not None:
            results = [
                t
                for t in results
                if t.transaction_type == filters.transaction_type
            ]

        return [self._to_response(t) for t in results]

    async def delete_transaction(
        self, transaction_id: int, user_id: int
    ) -> None:
        transaction = await self._uow.transactions.find_by_id(
            transaction_id, user_id
        )
        if transaction is None:
            raise TransactionNotFoundException(transaction_id)

        async with self._uow:
            deleted = await self._uow.transactions.delete(
                transaction_id, user_id
            )
            if not deleted:
                raise TransactionNotFoundException(transaction_id)

            await self._uow.outbox.add(
                event=TransactionDeletedEvent(
                    transaction_id=transaction_id,
                    account_id=transaction.account_id,
                    user_id=user_id,
                    amount=str(transaction.amount),
                ),
                aggregate_type="transaction",
                aggregate_id=str(transaction_id),
            )

            await self._uow.commit()

    async def import_csv(
        self, user_id: int, csv_content: str
    ) -> CSVImportResultDTO:
        reader = csv.DictReader(io.StringIO(csv_content))

        if reader.fieldnames is None:
            raise CSVImportException("CSV file is empty or has no headers")

        present = set(reader.fieldnames)
        missing = _CSV_REQUIRED_COLUMNS - present
        if missing:
            raise CSVImportException(
                f"CSV missing required columns: {', '.join(sorted(missing))}"
            )

        valid_rows: list[dict] = []
        errors: list[str] = []
        skipped = 0

        for row_num, row in enumerate(reader, start=2):
            try:
                amount = Decimal(row["amount"])
                if amount <= 0:
                    raise ValueError("amount must be positive")

                tx_type = row["transaction_type"].strip().lower()
                if tx_type not in ("income", "expense"):
                    raise ValueError(
                        f"invalid transaction_type: {tx_type}"
                    )

                valid_rows.append(
                    {
                        "user_id": user_id,
                        "account_id": int(row["account_id"]),
                        "account_name": row["account_name"].strip(),
                        "category_id": (
                            int(row["category_id"])
                            if row.get("category_id")
                            else None
                        ),
                        "category_name": (
                            row.get("category_name", "").strip() or None
                        ),
                        "amount": amount,
                        "transaction_type": tx_type,
                        "description": (
                            row.get("description", "").strip() or None
                        ),
                        "tx_date": date.fromisoformat(
                            row["date"].strip()
                        ),
                    }
                )
            except (ValueError, KeyError, InvalidOperation) as exc:
                errors.append(f"Row {row_num}: {exc}")
                skipped += 1

        if not valid_rows:
            return CSVImportResultDTO(
                imported=0, skipped=skipped, errors=errors
            )

        async with self._uow:
            created = await self._uow.transactions.bulk_create(valid_rows)

            outbox_entries = [
                (
                    TransactionCreatedEvent(
                        transaction_id=tx.id,
                        account_id=tx.account_id,
                        user_id=user_id,
                        amount=str(tx.amount),
                        category=tx.category_name or "",
                        description=tx.description or "",
                    ),
                    "transaction",
                    str(tx.id),
                )
                for tx in created
            ]
            await self._uow.outbox.add_batch(outbox_entries)

            await self._uow.commit()

        return CSVImportResultDTO(
            imported=len(created), skipped=skipped, errors=errors
        )

    # ── Planned transactions ────────────────────────────────────────

    async def create_planned(
        self, user_id: int, dto: CreatePlannedTransactionDTO
    ) -> PlannedTransactionResponse:
        async with self._uow:
            planned = await self._uow.planned.create(
                user_id=user_id,
                account_id=dto.account_id,
                account_name=dto.account_name,
                category_id=dto.category_id,
                category_name=dto.category_name,
                amount=dto.amount,
                transaction_type=dto.transaction_type,
                description=dto.description,
                recurrence=dto.recurrence,
                next_execution=dto.next_execution,
            )
            await self._uow.commit()
        return self._to_planned_response(planned)

    async def list_planned(
        self, user_id: int, active_only: bool = True
    ) -> list[PlannedTransactionResponse]:
        if active_only:
            results = await self._uow.planned.find_active(user_id)
        else:
            results = await self._uow.planned.find_by_user(user_id)
        return [self._to_planned_response(p) for p in results]

    async def update_planned(
        self,
        planned_id: int,
        user_id: int,
        dto: UpdatePlannedTransactionDTO,
    ) -> PlannedTransactionResponse:
        async with self._uow:
            existing = await self._uow.planned.find_by_id(
                planned_id, user_id
            )
            if existing is None:
                raise PlannedTransactionNotFoundException(planned_id)

            fields = dto.model_dump(exclude_unset=True)
            updated = await self._uow.planned.update(
                planned_id, user_id, **fields
            )
            await self._uow.commit()
        return self._to_planned_response(updated)

    async def deactivate_planned(
        self, planned_id: int, user_id: int
    ) -> None:
        async with self._uow:
            existing = await self._uow.planned.find_by_id(
                planned_id, user_id
            )
            if existing is None:
                raise PlannedTransactionNotFoundException(planned_id)
            await self._uow.planned.deactivate(planned_id, user_id)
            await self._uow.commit()

    # ── Mapping helpers ─────────────────────────────────────────────

    @staticmethod
    def _to_response(entity: Transaction) -> TransactionResponse:
        return TransactionResponse(
            id=entity.id,
            user_id=entity.user_id,
            account_id=entity.account_id,
            account_name=entity.account_name,
            category_id=entity.category_id,
            category_name=entity.category_name,
            amount=entity.amount,
            transaction_type=entity.transaction_type,
            description=entity.description,
            date=entity.date,
            created_at=entity.created_at,
        )

    @staticmethod
    def _to_planned_response(entity):  # type: ignore[no-untyped-def]
        return PlannedTransactionResponse(
            id=entity.id,
            user_id=entity.user_id,
            account_id=entity.account_id,
            account_name=entity.account_name,
            category_id=entity.category_id,
            category_name=entity.category_name,
            amount=entity.amount,
            transaction_type=entity.transaction_type,
            description=entity.description,
            recurrence=entity.recurrence,
            next_execution=entity.next_execution,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )
