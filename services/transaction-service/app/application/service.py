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
    SubcategoryMismatchException,
    SubcategoryNotFoundException,
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
        category_id = dto.category_id
        category_name = dto.category_name
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
                # Accept the categorizer's subcategory only when it doesn't
                # contradict a category the caller chose explicitly — the
                # caller's parent category always wins.
                if category_id is None:
                    category_id = cat_result.category_id
                    subcategory_id = cat_result.subcategory_id
                elif category_id == cat_result.category_id:
                    subcategory_id = cat_result.subcategory_id
                else:
                    logger.info(
                        "Categorizer suggested category %s but caller chose %s — keeping caller's, skipping subcategory",
                        cat_result.category_id,
                        category_id,
                    )
                cat_tier = cat_result.tier
                cat_confidence = cat_result.confidence
                logger.info(
                    "Sync categorization: '%s' -> cat=%s, sub=%s, tier=%s",
                    (dto.description or "")[:40],
                    category_id,
                    subcategory_id,
                    cat_result.tier,
                )
            else:
                logger.info(
                    "Categorization fallback for '%s' — async pipeline will retry",
                    (dto.description or "")[:40],
                )

        async with self._uow:
            # Names are resolved from the local read copies — callers may
            # send stale or missing names; ids are authoritative.
            category_name = await self._resolve_category_name(category_id, category_name)
            subcategory_name = await self._resolve_subcategory_name(subcategory_id)

            transaction = await self._uow.transactions.create(
                user_id=user_id,
                account_id=dto.account_id,
                account_name=dto.account_name,
                category_id=category_id,
                category_name=category_name,
                amount=dto.amount,
                transaction_type=dto.transaction_type,
                description=dto.description,
                tx_date=dto.date,
                subcategory_id=subcategory_id,
                subcategory_name=subcategory_name,
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
            results = await self._uow.transactions.find_filtered(
                user_id,
                account_id=filters.account_id,
                category_id=filters.category_id,
                start_date=filters.start_date,
                end_date=filters.end_date,
                transaction_type=filters.transaction_type,
                skip=filters.skip,
                limit=filters.limit,
            )
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

            # A manual category/subcategory edit pins the choice as
            # tier="manual" so the async categorization consumer won't
            # silently overwrite it.  If the parent category actually
            # changes, any previously-derived subcategory no longer
            # applies, so clear it (unless a new one is chosen in the
            # same request).
            if "category_id" in fields or "category_name" in fields or "subcategory_id" in fields:
                fields["categorization_tier"] = "manual"
                if "category_id" in fields and fields["category_id"] != existing.category_id:
                    fields.setdefault("subcategory_id", None)
                    fields.setdefault("subcategory_name", None)
                    # The name must match the new id — never trust a stale
                    # caller-provided name over the read copy.
                    fields["category_name"] = await self._resolve_category_name(
                        fields["category_id"], fields.get("category_name")
                    )

            if fields.get("subcategory_id") is not None:
                subcategory = await self._uow.subcategories.find_by_id(fields["subcategory_id"])
                if subcategory is None:
                    raise SubcategoryNotFoundException(fields["subcategory_id"])
                effective_category_id = fields.get("category_id", existing.category_id)
                if subcategory.category_id != effective_category_id:
                    raise SubcategoryMismatchException(subcategory.id, effective_category_id)
                fields["subcategory_name"] = subcategory.name
            elif "subcategory_id" in fields:
                # Explicit null clears both denormalized fields.
                fields["subcategory_name"] = None

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

        duplicates_skipped = 0
        rows_to_create: list[dict] = []

        async with self._uow:
            for row in parsed.rows:
                duplicate = await self._uow.transactions.find_duplicate(
                    user_id=user_id,
                    account_id=row["account_id"],
                    tx_date=row["tx_date"],
                    amount=row["amount"],
                    description=row.get("description"),
                )
                if duplicate is not None:
                    duplicates_skipped += 1
                    continue
                rows_to_create.append(row)

        if not rows_to_create:
            return CSVImportResultDTO(
                imported=0,
                skipped=parsed.skipped,
                duplicates_skipped=duplicates_skipped,
                errors=parsed.errors,
            )

        async with self._uow:
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

        return CSVImportResultDTO(
            imported=len(created),
            skipped=parsed.skipped,
            duplicates_skipped=duplicates_skipped,
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
                    row = rows_to_create[idx]
                    # Same rule as create_transaction: the producer's explicit
                    # parent category wins over the categorizer's suggestion.
                    if row.get("category_id") is None:
                        row["category_id"] = cat_result.category_id
                        row["subcategory_id"] = cat_result.subcategory_id
                    elif row["category_id"] == cat_result.category_id:
                        row["subcategory_id"] = cat_result.subcategory_id
                    row["categorization_tier"] = cat_result.tier
                    row["categorization_confidence"] = cat_result.confidence
                    enriched += 1
            if enriched:
                logger.info("Bulk categorization: %d/%d items enriched", enriched, len(uncategorized))

        async with self._uow:
            await self._resolve_names_for_rows(rows_to_create)
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

    # ── Name resolution (local taxonomy read copies) ────────────────

    async def _resolve_category_name(
        self,
        category_id: int | None,
        fallback: str | None = None,
    ) -> str | None:
        """Parent name from the local read copy; ids are authoritative.

        Falls back to the caller-provided name only when the id isn't in
        the read copy yet (sync lag) — better a possibly-stale name than
        none at all.
        """
        if category_id is None:
            return fallback
        category = await self._uow.categories.find_by_id(category_id)
        if category is None:
            return fallback
        return category.name

    async def _resolve_subcategory_name(self, subcategory_id: int | None) -> str | None:
        if subcategory_id is None:
            return None
        subcategory = await self._uow.subcategories.find_by_id(subcategory_id)
        return subcategory.name if subcategory else None

    async def _resolve_names_for_rows(self, rows: list[dict]) -> None:
        """Batch-resolve denormalized names on bulk rows in place."""
        category_ids = {row["category_id"] for row in rows if row.get("category_id") is not None}
        subcategory_ids = [row["subcategory_id"] for row in rows if row.get("subcategory_id") is not None]

        category_names: dict[int, str] = {}
        for cat_id in category_ids:
            category = await self._uow.categories.find_by_id(cat_id)
            if category is not None:
                category_names[cat_id] = category.name

        subcategories = await self._uow.subcategories.find_by_ids(subcategory_ids)

        for row in rows:
            cat_id = row.get("category_id")
            if cat_id is not None and cat_id in category_names:
                row["category_name"] = category_names[cat_id]
            sub_id = row.get("subcategory_id")
            if sub_id is not None and sub_id in subcategories:
                row["subcategory_name"] = subcategories[sub_id].name

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
            subcategory_id=entity.subcategory_id,
            subcategory_name=entity.subcategory_name,
            categorization_tier=entity.categorization_tier,
            categorization_confidence=entity.categorization_confidence,
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
