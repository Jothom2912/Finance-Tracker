from __future__ import annotations

import logging

from contracts.events.transaction import (
    TransactionCreatedEvent,
    TransactionDeletedEvent,
    TransactionUpdatedEvent,
)

from app.application.csv_parsers.registry import get_parser
from app.application.dto import (
    BulkCreateResultDTO,
    BulkCreateTransactionDTO,
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    CSVImportResultDTO,
    PlannedTransactionResponse,
    TransactionFiltersDTO,
    TransactionResponse,
    UpdatePlannedTransactionDTO,
    UpdateTransactionDTO,
)
from app.application.ports.inbound import ITransactionService
from app.application.ports.outbound import IUnitOfWork
from app.domain.entities import PlannedTransaction, Transaction
from app.domain.exceptions import (
    CSVImportException,
    PlannedTransactionNotFoundException,
    TransactionNotFoundException,
)

logger = logging.getLogger(__name__)


class TransactionService(ITransactionService):
    """Application service for financial transactions.

    Uses a Unit of Work that exposes transaction/planned repos and
    a transactional outbox.  Domain writes and event-intent rows
    are committed atomically — the outbox publisher worker handles
    delivery to RabbitMQ independently.

    The optional ``categorization_client`` calls categorization-service's
    sync /categorize endpoint (tier 1 rule engine) before persisting.
    If the client is None or the call fails, transactions are saved
    without categorization — the async pipeline picks them up via
    the transaction.created event.
    """

    def __init__(
        self,
        uow: IUnitOfWork,
        categorization_client: object | None = None,
    ) -> None:
        self._uow = uow
        self._cat_client = categorization_client

    # ── Transactions ────────────────────────────────────────────────

    async def create_transaction(self, user_id: int, dto: CreateTransactionDTO) -> TransactionResponse:
        subcategory_id = dto.subcategory_id
        cat_tier = dto.categorization_tier
        cat_confidence = dto.categorization_confidence

        already_categorized = cat_tier is not None and cat_tier != "fallback"
        if not already_categorized and self._cat_client is not None:
            cat_result = await self._cat_client.categorize(
                description=dto.description or "",
                amount=float(dto.amount),
            )
            if cat_result is not None:
                subcategory_id = cat_result.subcategory_id
                cat_tier = cat_result.tier
                cat_confidence = cat_result.confidence
                logger.info(
                    "Sync categorization: '%s' -> sub=%d, tier=%s",
                    (dto.description or "")[:40],
                    cat_result.subcategory_id,
                    cat_result.tier,
                )
            else:
                logger.info(
                    "Categorization fallback for '%s' — async pipeline will retry",
                    (dto.description or "")[:40],
                )

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
                subcategory_id=subcategory_id,
                categorization_tier=cat_tier,
                categorization_confidence=cat_confidence,
            )

            await self._uow.outbox.add(
                event=TransactionCreatedEvent(
                    transaction_id=transaction.id,
                    account_id=transaction.account_id,
                    user_id=user_id,
                    amount=str(transaction.amount),
                    transaction_type=transaction.transaction_type.value,
                    tx_date=transaction.date,
                    category_id=transaction.category_id,
                    category=transaction.category_name or "",
                    description=transaction.description or "",
                    account_name=transaction.account_name or "",
                    subcategory_id=transaction.subcategory_id,
                    categorization_tier=transaction.categorization_tier,
                    categorization_confidence=transaction.categorization_confidence,
                ),
                aggregate_type="transaction",
                aggregate_id=str(transaction.id),
            )

            await self._uow.commit()

        return self._to_response(transaction)

    async def get_transaction(self, transaction_id: int, user_id: int) -> TransactionResponse:
        async with self._uow:
            transaction = await self._uow.transactions.find_by_id(transaction_id, user_id)
        if transaction is None:
            raise TransactionNotFoundException(transaction_id)
        return self._to_response(transaction)

    async def list_transactions(self, user_id: int, filters: TransactionFiltersDTO) -> list[TransactionResponse]:
        async with self._uow:
            if filters.account_id is not None:
                results = await self._uow.transactions.find_by_account(filters.account_id, user_id)
            elif filters.category_id is not None:
                results = await self._uow.transactions.find_by_category(filters.category_id, user_id)
            elif filters.start_date is not None and filters.end_date is not None:
                results = await self._uow.transactions.find_by_date_range(user_id, filters.start_date, filters.end_date)
            else:
                results = await self._uow.transactions.find_by_user(user_id, skip=filters.skip, limit=filters.limit)

        if filters.transaction_type is not None:
            results = [t for t in results if t.transaction_type == filters.transaction_type]

        return [self._to_response(t) for t in results]

    async def update_transaction(
        self,
        transaction_id: int,
        user_id: int,
        dto: UpdateTransactionDTO,
    ) -> TransactionResponse:
        fields = dto.model_dump(exclude_unset=True)

        async with self._uow:
            existing = await self._uow.transactions.find_by_id(transaction_id, user_id)
            if existing is None:
                raise TransactionNotFoundException(transaction_id)

            if not fields:
                return self._to_response(existing)

            previous_amount = existing.amount
            previous_category = existing.category_name or ""

            updated = await self._uow.transactions.update(transaction_id, user_id, **fields)

            await self._uow.outbox.add(
                event=TransactionUpdatedEvent(
                    transaction_id=updated.id,
                    account_id=updated.account_id,
                    user_id=user_id,
                    amount=str(updated.amount),
                    previous_amount=str(previous_amount),
                    transaction_type=updated.transaction_type.value,
                    tx_date=updated.date,
                    category_id=updated.category_id,
                    category=updated.category_name or "",
                    previous_category=previous_category,
                    description=updated.description or "",
                    account_name=updated.account_name or "",
                    subcategory_id=updated.subcategory_id,
                    categorization_tier=updated.categorization_tier,
                    categorization_confidence=updated.categorization_confidence,
                ),
                aggregate_type="transaction",
                aggregate_id=str(updated.id),
            )

            await self._uow.commit()

        return self._to_response(updated)

    async def delete_transaction(self, transaction_id: int, user_id: int) -> None:
        async with self._uow:
            transaction = await self._uow.transactions.find_by_id(transaction_id, user_id)
            if transaction is None:
                raise TransactionNotFoundException(transaction_id)

            deleted = await self._uow.transactions.delete(transaction_id, user_id)
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
        self,
        user_id: int,
        csv_content: bytes,
        bank_format: str = "internal",
        account_id: int | None = None,
        account_name: str | None = None,
    ) -> CSVImportResultDTO:
        if bank_format != "internal" and (account_id is None or not account_name):
            raise CSVImportException(f"account_id and account_name are required for bank format {bank_format!r}")

        parser = get_parser(bank_format)
        parsed = parser.parse(
            file_content=csv_content,
            user_id=user_id,
            account_id=account_id or 0,
            account_name=account_name or "",
        )

        if not parsed.rows:
            return CSVImportResultDTO(imported=0, skipped=parsed.skipped, errors=parsed.errors)

        async with self._uow:
            created = await self._uow.transactions.bulk_create(parsed.rows)

            outbox_entries = [
                (
                    TransactionCreatedEvent(
                        transaction_id=tx.id,
                        account_id=tx.account_id,
                        user_id=user_id,
                        amount=str(tx.amount),
                        transaction_type=tx.transaction_type.value,
                        tx_date=tx.date,
                        category_id=tx.category_id,
                        category=tx.category_name or "",
                        description=tx.description or "",
                        account_name=tx.account_name or "",
                        subcategory_id=tx.subcategory_id,
                        categorization_tier=tx.categorization_tier,
                        categorization_confidence=tx.categorization_confidence,
                    ),
                    "transaction",
                    str(tx.id),
                )
                for tx in created
            ]
            await self._uow.outbox.add_batch(outbox_entries)

            await self._uow.commit()

        return CSVImportResultDTO(
            imported=len(created),
            skipped=parsed.skipped,
            errors=parsed.errors,
        )

    async def bulk_import(
        self,
        user_id: int,
        dto: BulkCreateTransactionDTO,
    ) -> BulkCreateResultDTO:
        """Server-side bulk import used by trusted internal producers
        (e.g. the banking module when syncing bank transactions).

        Performs deduplication on ``(user_id, account_id, date, amount,
        description)`` and publishes one ``TransactionCreatedEvent``
        per newly inserted row via the outbox.

        If items lack categorization metadata and a categorization client
        is available, a batch sync call enriches them before persist.
        """
        duplicates_skipped = 0
        errors = 0
        rows_to_create: list[dict] = []

        async with self._uow:
            for item in dto.items:
                try:
                    if dto.skip_duplicates:
                        duplicate = await self._uow.transactions.find_duplicate(
                            user_id=user_id,
                            account_id=item.account_id,
                            tx_date=item.date,
                            amount=item.amount,
                            description=item.description,
                        )
                        if duplicate is not None:
                            duplicates_skipped += 1
                            continue

                    rows_to_create.append(
                        {
                            "user_id": user_id,
                            "account_id": item.account_id,
                            "account_name": item.account_name,
                            "category_id": item.category_id,
                            "category_name": item.category_name,
                            "amount": item.amount,
                            "transaction_type": item.transaction_type,
                            "description": item.description,
                            "tx_date": item.date,
                            "subcategory_id": item.subcategory_id,
                            "categorization_tier": item.categorization_tier,
                            "categorization_confidence": item.categorization_confidence,
                        }
                    )
                except Exception:
                    logger.exception("Bulk-import validation failed for item")
                    errors += 1

        uncategorized = [
            i
            for i, row in enumerate(rows_to_create)
            if not row.get("categorization_tier") or row.get("categorization_tier") == "fallback"
        ]

        if uncategorized and self._cat_client is not None:
            batch_items = [
                {
                    "description": rows_to_create[i].get("description") or "",
                    "amount": float(rows_to_create[i]["amount"]),
                }
                for i in uncategorized
            ]
            cat_results = await self._cat_client.categorize_batch(batch_items)
            enriched = 0
            for idx, cat_result in zip(uncategorized, cat_results):
                if cat_result is not None:
                    rows_to_create[idx]["subcategory_id"] = cat_result.subcategory_id
                    rows_to_create[idx]["categorization_tier"] = cat_result.tier
                    rows_to_create[idx]["categorization_confidence"] = cat_result.confidence
                    enriched += 1
            if enriched:
                logger.info("Bulk categorization: %d/%d items enriched", enriched, len(uncategorized))

        async with self._uow:
            if not rows_to_create:
                await self._uow.commit()
                return BulkCreateResultDTO(
                    imported=0,
                    duplicates_skipped=duplicates_skipped,
                    errors=errors,
                    imported_ids=[],
                )

            created = await self._uow.transactions.bulk_create(rows_to_create)

            outbox_entries = [
                (
                    TransactionCreatedEvent(
                        transaction_id=tx.id,
                        account_id=tx.account_id,
                        user_id=user_id,
                        amount=str(tx.amount),
                        transaction_type=tx.transaction_type.value,
                        tx_date=tx.date,
                        category_id=tx.category_id,
                        category=tx.category_name or "",
                        description=tx.description or "",
                        account_name=tx.account_name or "",
                        subcategory_id=tx.subcategory_id,
                        categorization_tier=tx.categorization_tier,
                        categorization_confidence=tx.categorization_confidence,
                    ),
                    "transaction",
                    str(tx.id),
                )
                for tx in created
            ]
            await self._uow.outbox.add_batch(outbox_entries)

            await self._uow.commit()

        return BulkCreateResultDTO(
            imported=len(created),
            duplicates_skipped=duplicates_skipped,
            errors=errors,
            imported_ids=[tx.id for tx in created],
        )

    # ── Planned transactions ────────────────────────────────────────

    async def create_planned(self, user_id: int, dto: CreatePlannedTransactionDTO) -> PlannedTransactionResponse:
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

    async def list_planned(self, user_id: int, active_only: bool = True) -> list[PlannedTransactionResponse]:
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
            existing = await self._uow.planned.find_by_id(planned_id, user_id)
            if existing is None:
                raise PlannedTransactionNotFoundException(planned_id)

            fields = dto.model_dump(exclude_unset=True)
            updated = await self._uow.planned.update(planned_id, user_id, **fields)
            await self._uow.commit()
        return self._to_planned_response(updated)

    async def deactivate_planned(self, planned_id: int, user_id: int) -> None:
        async with self._uow:
            existing = await self._uow.planned.find_by_id(planned_id, user_id)
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
    def _to_planned_response(entity: PlannedTransaction) -> PlannedTransactionResponse:
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
