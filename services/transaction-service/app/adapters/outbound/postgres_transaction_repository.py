from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import DedupKey, ExternalIdKey, ITransactionRepository
from app.domain.entities import Transaction, TransactionType
from app.models import TransactionModel


class PostgresTransactionRepository(ITransactionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: int,
        account_id: int,
        account_name: str,
        category_id: int | None,
        category_name: str | None,
        amount: Decimal,
        transaction_type: TransactionType,
        description: str | None,
        tx_date: date,
        subcategory_id: int | None = None,
        subcategory_name: str | None = None,
        categorization_tier: str | None = None,
        categorization_confidence: str | None = None,
    ) -> Transaction:
        model = TransactionModel(
            user_id=user_id,
            account_id=account_id,
            account_name=account_name,
            category_id=category_id,
            category_name=category_name,
            amount=amount,
            transaction_type=transaction_type.value,
            description=description,
            date=tx_date,
            subcategory_id=subcategory_id,
            subcategory_name=subcategory_name,
            categorization_tier=categorization_tier,
            categorization_confidence=categorization_confidence,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def find_by_id(self, transaction_id: int, user_id: int) -> Transaction | None:
        stmt = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def find_filtered(
        self,
        user_id: int,
        account_id: int | None = None,
        category_id: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        transaction_type: TransactionType | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Transaction]:
        """Single filtered listing query — every provided filter is
        applied in SQL, combined with AND, plus OFFSET/LIMIT pagination.

        Ordering is date desc with id desc as tie-breaker so pagination
        is deterministic for same-date rows.
        """
        stmt = select(TransactionModel).where(TransactionModel.user_id == user_id)
        if account_id is not None:
            stmt = stmt.where(TransactionModel.account_id == account_id)
        if category_id is not None:
            stmt = stmt.where(TransactionModel.category_id == category_id)
        if start_date is not None:
            stmt = stmt.where(TransactionModel.date >= start_date)
        if end_date is not None:
            stmt = stmt.where(TransactionModel.date <= end_date)
        if transaction_type is not None:
            stmt = stmt.where(TransactionModel.transaction_type == transaction_type.value)
        stmt = stmt.order_by(TransactionModel.date.desc(), TransactionModel.id.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, transaction_id: int, user_id: int, **fields: object) -> Transaction:
        stmt = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            from app.domain.exceptions import TransactionNotFoundException

            raise TransactionNotFoundException(transaction_id)

        for key, value in fields.items():
            if key == "transaction_type" and value is not None:
                value = value.value if isinstance(value, TransactionType) else value
            setattr(model, key, value)

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def delete(self, transaction_id: int, user_id: int) -> bool:
        stmt = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    # Rows per tuple_(...).in_() batch — 3 bind params per triple keeps
    # us far below asyncpg's 32767-parameter limit even for large files.
    _DEDUP_CHUNK_SIZE = 500

    async def find_existing_dedup_keys(
        self,
        user_id: int,
        keys: list[DedupKey],
        *,
        only_missing_external_id: bool = False,
    ) -> set[DedupKey]:
        """Batch anti-join for the bank-sync dedup key
        ``(user_id, account_id, date, amount, description)``.

        The SQL matches on the ``(account_id, date, amount)`` triples
        (served by the composite index from migration 011) and the
        description is compared in Python — ``tuple_(...).in_()`` can't
        match NULL descriptions, and NULL-vs-None semantics are exact
        this way.  The candidate set fetched is a small superset of the
        true matches (rows differing only in description).

        ``only_missing_external_id`` scopes the match to rows with no
        external_id (legacy/manual/CSV) — the transition fallback for
        id-bearing bank imports (see the port docstring).
        """
        if not keys:
            return set()

        triples = sorted({(account_id, tx_date, amount) for account_id, tx_date, amount, _ in keys})
        candidate_keys: set[DedupKey] = set()

        for start in range(0, len(triples), self._DEDUP_CHUNK_SIZE):
            chunk = triples[start : start + self._DEDUP_CHUNK_SIZE]
            stmt = select(
                TransactionModel.account_id,
                TransactionModel.date,
                TransactionModel.amount,
                TransactionModel.description,
            ).where(
                TransactionModel.user_id == user_id,
                tuple_(
                    TransactionModel.account_id,
                    TransactionModel.date,
                    TransactionModel.amount,
                ).in_(chunk),
            )
            if only_missing_external_id:
                stmt = stmt.where(TransactionModel.external_id.is_(None))
            result = await self._session.execute(stmt)
            candidate_keys.update((row.account_id, row.date, row.amount, row.description) for row in result)

        return candidate_keys & set(keys)

    async def find_existing_external_ids(
        self,
        user_id: int,
        keys: list[ExternalIdKey],
    ) -> set[ExternalIdKey]:
        """Batch anti-join on ``(account_id, external_id)`` — served by
        the partial unique index from migration 012.  Keys never contain
        NULL external_ids (callers filter), so no Python-side matching
        is needed.
        """
        if not keys:
            return set()

        pairs = sorted(set(keys))
        existing: set[ExternalIdKey] = set()

        for start in range(0, len(pairs), self._DEDUP_CHUNK_SIZE):
            chunk = pairs[start : start + self._DEDUP_CHUNK_SIZE]
            stmt = select(
                TransactionModel.account_id,
                TransactionModel.external_id,
            ).where(
                TransactionModel.user_id == user_id,
                tuple_(
                    TransactionModel.account_id,
                    TransactionModel.external_id,
                ).in_(chunk),
            )
            result = await self._session.execute(stmt)
            existing.update((row.account_id, row.external_id) for row in result)

        return existing

    async def bulk_create(self, transactions: list[dict]) -> list[Transaction]:
        models = []
        for tx in transactions:
            tx_type = tx.get("transaction_type", "expense")
            if isinstance(tx_type, TransactionType):
                tx_type = tx_type.value
            models.append(
                TransactionModel(
                    user_id=tx["user_id"],
                    account_id=tx["account_id"],
                    account_name=tx["account_name"],
                    category_id=tx.get("category_id"),
                    category_name=tx.get("category_name"),
                    amount=tx["amount"],
                    transaction_type=tx_type,
                    description=tx.get("description"),
                    date=tx["tx_date"],
                    subcategory_id=tx.get("subcategory_id"),
                    subcategory_name=tx.get("subcategory_name"),
                    categorization_tier=tx.get("categorization_tier"),
                    categorization_confidence=tx.get("categorization_confidence"),
                    external_id=tx.get("external_id"),
                    currency=tx.get("currency", "DKK"),
                )
            )
        self._session.add_all(models)
        await self._session.flush()
        for m in models:
            await self._session.refresh(m)
        return [self._to_entity(m) for m in models]

    @staticmethod
    def _to_entity(model: TransactionModel) -> Transaction:
        return Transaction(
            id=model.id,
            user_id=model.user_id,
            account_id=model.account_id,
            account_name=model.account_name,
            category_id=model.category_id,
            category_name=model.category_name,
            amount=model.amount,
            transaction_type=TransactionType(model.transaction_type),
            description=model.description,
            date=model.date,
            created_at=model.created_at,
            subcategory_id=model.subcategory_id,
            subcategory_name=model.subcategory_name,
            categorization_tier=model.categorization_tier,
            categorization_confidence=model.categorization_confidence,
            external_id=model.external_id,
            currency=model.currency,
        )
