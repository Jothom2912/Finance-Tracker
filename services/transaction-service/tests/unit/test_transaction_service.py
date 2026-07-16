from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.dto import (
    BulkCreateTransactionDTO,
    BulkCreateTransactionItemDTO,
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    TransactionFiltersDTO,
    UpdateTransactionDTO,
)
from app.application.service import TransactionService
from app.domain.entities import (
    Category,
    CategoryType,
    PlannedTransaction,
    SubCategory,
    Transaction,
    TransactionType,
)
from app.domain.exceptions import (
    CSVImportException,
    PlannedTransactionNotFoundException,
    SubcategoryMismatchException,
    SubcategoryNotFoundException,
    TransactionNotFoundException,
)


def _make_transaction(**overrides) -> Transaction:  # type: ignore[no-untyped-def]
    defaults = {
        "id": 1,
        "user_id": 10,
        "account_id": 100,
        "account_name": "Main Account",
        "category_id": 5,
        "category_name": "Food",
        "amount": Decimal("49.99"),
        "transaction_type": TransactionType.EXPENSE,
        "description": "Groceries",
        "date": date(2026, 3, 1),
        "created_at": datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return Transaction(**defaults)


def _make_planned(**overrides) -> PlannedTransaction:  # type: ignore[no-untyped-def]
    defaults = {
        "id": 1,
        "user_id": 10,
        "account_id": 100,
        "account_name": "Main Account",
        "category_id": 5,
        "category_name": "Rent",
        "amount": Decimal("5000.00"),
        "transaction_type": TransactionType.EXPENSE,
        "description": "Monthly rent",
        "recurrence": "monthly",
        "next_execution": date(2026, 4, 1),
        "is_active": True,
        "created_at": datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return PlannedTransaction(**defaults)


def _build_service():  # type: ignore[no-untyped-def]
    """Build service with mock UoW exposing repos and outbox."""
    uow = MagicMock()
    uow.transactions = AsyncMock()
    uow.planned = AsyncMock()
    uow.outbox = AsyncMock()
    # Taxonomy read copies: default to "id unknown" so name resolution
    # falls back to caller-provided names unless a test stubs them.
    uow.categories = AsyncMock()
    uow.categories.find_by_id.return_value = None
    uow.subcategories = AsyncMock()
    uow.subcategories.find_by_id.return_value = None
    uow.subcategories.find_by_ids.return_value = {}
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    service = TransactionService(uow=uow)
    return service, uow


class TestCreateTransaction:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        tx = _make_transaction()
        uow.transactions.create.return_value = tx
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            category_id=5,
            category_name="Food",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            description="Groceries",
            date=date(2026, 3, 1),
        )

        result = await service.create_transaction(user_id=10, dto=dto)

        uow.transactions.create.assert_awaited_once()
        uow.commit.assert_awaited_once()
        assert result.id == 1
        assert result.amount == Decimal("49.99")

    @pytest.mark.asyncio()
    async def test_writes_outbox_event(self) -> None:
        service, uow = _build_service()
        uow.transactions.create.return_value = _make_transaction()
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 3, 1),
        )

        await service.create_transaction(user_id=10, dto=dto)

        uow.outbox.add.assert_awaited_once()
        call_kwargs = uow.outbox.add.call_args[1]
        event = call_kwargs["event"]
        assert event.event_type == "transaction.created"
        assert event.transaction_id == 1
        assert event.user_id == 10
        assert event.amount == "49.99"
        assert call_kwargs["aggregate_type"] == "transaction"
        assert call_kwargs["aggregate_id"] == "1"

    @pytest.mark.asyncio()
    async def test_categorization_metadata_forwarded_on_create(self) -> None:
        """Create-transaction DTOs may carry pipeline metadata from
        the rule-engine categoriser; both the repository call and
        the outbox event must carry them through.
        """
        service, uow = _build_service()
        uow.transactions.create.return_value = _make_transaction(
            subcategory_id=42,
            categorization_tier="rule",
            categorization_confidence="high",
        )
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            category_id=5,
            category_name="Food",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            description="Groceries",
            date=date(2026, 3, 1),
            subcategory_id=42,
            categorization_tier="rule",
            categorization_confidence="high",
        )

        await service.create_transaction(user_id=10, dto=dto)

        repo_kwargs = uow.transactions.create.call_args.kwargs
        assert repo_kwargs["subcategory_id"] == 42
        assert repo_kwargs["categorization_tier"] == "rule"
        assert repo_kwargs["categorization_confidence"] == "high"

        event = uow.outbox.add.call_args.kwargs["event"]
        assert event.subcategory_id == 42
        assert event.categorization_tier == "rule"
        assert event.categorization_confidence == "high"

    @pytest.mark.asyncio()
    async def test_sync_categorization_copies_category_and_resolves_names(self) -> None:
        """When the caller provides no category, the categorizer's
        category_id AND subcategory_id are applied, and both denormalized
        names are resolved from the local read copies."""
        service, uow = _build_service()
        cat_client = AsyncMock()
        cat_client.categorize.return_value = MagicMock(
            category_id=1,
            subcategory_id=3,
            tier="rule",
            confidence="high",
        )
        service._cat_client = cat_client
        uow.categories.find_by_id.return_value = Category(
            id=1,
            name="Mad & drikke",
            type=CategoryType.EXPENSE,
        )
        uow.subcategories.find_by_id.return_value = SubCategory(
            id=3,
            name="Takeaway",
            category_id=1,
        )
        uow.transactions.create.return_value = _make_transaction()
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            description="Wolt",
            date=date(2026, 3, 1),
        )

        await service.create_transaction(user_id=10, dto=dto)

        repo_kwargs = uow.transactions.create.call_args.kwargs
        assert repo_kwargs["category_id"] == 1
        assert repo_kwargs["category_name"] == "Mad & drikke"
        assert repo_kwargs["subcategory_id"] == 3
        assert repo_kwargs["subcategory_name"] == "Takeaway"

    @pytest.mark.asyncio()
    async def test_sync_categorization_conflict_keeps_callers_category(self) -> None:
        """A caller-chosen parent category wins over the categorizer's
        suggestion; the conflicting subcategory is skipped to avoid a
        parent/child mismatch."""
        service, uow = _build_service()
        cat_client = AsyncMock()
        cat_client.categorize.return_value = MagicMock(
            category_id=1,
            subcategory_id=3,
            tier="rule",
            confidence="high",
        )
        service._cat_client = cat_client
        uow.transactions.create.return_value = _make_transaction()
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            category_id=2,
            category_name="Bolig",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            description="Wolt",
            date=date(2026, 3, 1),
        )

        await service.create_transaction(user_id=10, dto=dto)

        repo_kwargs = uow.transactions.create.call_args.kwargs
        assert repo_kwargs["category_id"] == 2
        assert repo_kwargs["subcategory_id"] is None

    @pytest.mark.asyncio()
    async def test_outbox_before_commit(self) -> None:
        """Outbox add and commit happen inside same UoW context."""
        service, uow = _build_service()
        uow.transactions.create.return_value = _make_transaction()
        call_order: list[str] = []
        uow.outbox.add.side_effect = lambda **kw: call_order.append("outbox")
        uow.commit.side_effect = lambda: call_order.append("commit")
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 3, 1),
        )

        await service.create_transaction(user_id=10, dto=dto)

        assert call_order == ["outbox", "commit"]


class TestGetTransaction:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_by_id.return_value = _make_transaction()

        result = await service.get_transaction(transaction_id=1, user_id=10)

        assert result.id == 1
        uow.transactions.find_by_id.assert_awaited_once_with(1, 10)

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_by_id.return_value = None

        with pytest.raises(TransactionNotFoundException):
            await service.get_transaction(transaction_id=99, user_id=10)


class TestListTransactions:
    @pytest.mark.asyncio()
    async def test_with_date_filter(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_filtered.return_value = [_make_transaction()]
        filters = TransactionFiltersDTO(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

        results = await service.list_transactions(user_id=10, filters=filters)

        uow.transactions.find_filtered.assert_awaited_once_with(
            10,
            account_id=None,
            category_id=None,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            transaction_type=None,
            skip=0,
            limit=50,
        )
        assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_combined_filters_forwarded_in_one_query(self) -> None:
        """account + date range + type + pagination must reach the
        repository together — no filter may be silently dropped."""
        service, uow = _build_service()
        uow.transactions.find_filtered.return_value = [_make_transaction()]
        filters = TransactionFiltersDTO(
            account_id=100,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            transaction_type=TransactionType.EXPENSE,
            skip=10,
            limit=25,
        )

        results = await service.list_transactions(user_id=10, filters=filters)

        uow.transactions.find_filtered.assert_awaited_once_with(
            10,
            account_id=100,
            category_id=None,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            transaction_type=TransactionType.EXPENSE,
            skip=10,
            limit=25,
        )
        assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_default_pagination(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_filtered.return_value = []
        filters = TransactionFiltersDTO()

        await service.list_transactions(user_id=10, filters=filters)

        uow.transactions.find_filtered.assert_awaited_once_with(
            10,
            account_id=None,
            category_id=None,
            start_date=None,
            end_date=None,
            transaction_type=None,
            skip=0,
            limit=50,
        )


class TestUpdateTransaction:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        existing = _make_transaction()
        updated = _make_transaction(amount=Decimal("75.00"), description="Updated")
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = updated
        dto = UpdateTransactionDTO(amount=Decimal("75.00"), description="Updated")

        result = await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        uow.transactions.update.assert_awaited_once()
        uow.commit.assert_awaited_once()
        assert result.amount == Decimal("75.00")
        assert result.description == "Updated"

    @pytest.mark.asyncio()
    async def test_writes_outbox_event_with_previous_values(self) -> None:
        service, uow = _build_service()
        existing = _make_transaction(
            amount=Decimal("49.99"),
            category_name="Food",
        )
        updated = _make_transaction(
            amount=Decimal("75.00"),
            category_name="Transport",
        )
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = updated
        dto = UpdateTransactionDTO(
            amount=Decimal("75.00"),
            category_id=10,
            category_name="Transport",
        )

        await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        uow.outbox.add.assert_awaited_once()
        event = uow.outbox.add.call_args[1]["event"]
        assert event.event_type == "transaction.updated"
        assert event.amount == "75.00"
        assert event.previous_amount == "49.99"
        assert event.category == "Transport"
        assert event.previous_category == "Food"

    @pytest.mark.asyncio()
    async def test_manual_category_change_pins_tier_and_clears_subcategory(self) -> None:
        """A manual parent-category edit must pin tier="manual" (so the async
        categorization consumer won't overwrite it) and clear the now-stale
        subcategory, since the previously-derived sub no longer belongs to the
        new parent."""
        service, uow = _build_service()
        existing = _make_transaction(
            category_id=5,
            subcategory_id=42,
            categorization_tier="rule",
        )
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = _make_transaction(category_id=10)
        dto = UpdateTransactionDTO(category_id=10, category_name="Transport")

        await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        fields = uow.transactions.update.call_args.kwargs
        assert fields["categorization_tier"] == "manual"
        assert fields["subcategory_id"] is None
        assert fields["subcategory_name"] is None

    @pytest.mark.asyncio()
    async def test_category_name_only_edit_pins_manual_without_clearing_subcategory(self) -> None:
        """Renaming/setting category_name without changing category_id pins the
        choice as manual but must NOT clear the subcategory — the parent is
        unchanged, so the derived sub still applies."""
        service, uow = _build_service()
        existing = _make_transaction(category_id=5, subcategory_id=42)
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = _make_transaction()
        dto = UpdateTransactionDTO(category_name="Mad & drikke")

        await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        fields = uow.transactions.update.call_args.kwargs
        assert fields["categorization_tier"] == "manual"
        assert "subcategory_id" not in fields
        assert "subcategory_name" not in fields

    @pytest.mark.asyncio()
    async def test_non_category_edit_does_not_pin_manual(self) -> None:
        """Editing only amount/description must leave categorization metadata
        untouched, so the async consumer can still categorize the row."""
        service, uow = _build_service()
        existing = _make_transaction(category_id=5)
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = _make_transaction(amount=Decimal("75.00"))
        dto = UpdateTransactionDTO(amount=Decimal("75.00"))

        await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        fields = uow.transactions.update.call_args.kwargs
        assert "categorization_tier" not in fields

    @pytest.mark.asyncio()
    async def test_subcategory_edit_resolves_name_and_pins_manual(self) -> None:
        """Choosing a subcategory validates it against the local read copy,
        resolves subcategory_name server-side, and pins tier=manual so the
        async consumer won't overwrite the user's choice."""
        service, uow = _build_service()
        existing = _make_transaction(category_id=5, subcategory_id=None)
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = _make_transaction(subcategory_id=42)
        uow.subcategories.find_by_id.return_value = SubCategory(
            id=42,
            name="Dagligvarer",
            category_id=5,
        )
        dto = UpdateTransactionDTO(subcategory_id=42)

        await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        fields = uow.transactions.update.call_args.kwargs
        assert fields["subcategory_id"] == 42
        assert fields["subcategory_name"] == "Dagligvarer"
        assert fields["categorization_tier"] == "manual"

    @pytest.mark.asyncio()
    async def test_subcategory_must_belong_to_effective_category(self) -> None:
        service, uow = _build_service()
        existing = _make_transaction(category_id=5)
        uow.transactions.find_by_id.return_value = existing
        uow.subcategories.find_by_id.return_value = SubCategory(
            id=42,
            name="Husleje",
            category_id=2,
        )
        dto = UpdateTransactionDTO(subcategory_id=42)

        with pytest.raises(SubcategoryMismatchException):
            await service.update_transaction(transaction_id=1, user_id=10, dto=dto)
        uow.commit.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_subcategory_validated_against_new_category_when_both_change(self) -> None:
        service, uow = _build_service()
        existing = _make_transaction(category_id=5)
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = _make_transaction(category_id=2, subcategory_id=6)
        uow.subcategories.find_by_id.return_value = SubCategory(
            id=6,
            name="Husleje",
            category_id=2,
        )
        uow.categories.find_by_id.return_value = Category(
            id=2,
            name="Bolig",
            type=CategoryType.EXPENSE,
        )
        dto = UpdateTransactionDTO(category_id=2, subcategory_id=6)

        await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        fields = uow.transactions.update.call_args.kwargs
        assert fields["subcategory_id"] == 6
        assert fields["subcategory_name"] == "Husleje"
        assert fields["category_name"] == "Bolig"

    @pytest.mark.asyncio()
    async def test_unknown_subcategory_raises_404(self) -> None:
        service, uow = _build_service()
        existing = _make_transaction(category_id=5)
        uow.transactions.find_by_id.return_value = existing
        uow.subcategories.find_by_id.return_value = None
        dto = UpdateTransactionDTO(subcategory_id=999)

        with pytest.raises(SubcategoryNotFoundException):
            await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

    @pytest.mark.asyncio()
    async def test_explicit_null_subcategory_clears_both_fields(self) -> None:
        service, uow = _build_service()
        existing = _make_transaction(category_id=5, subcategory_id=42)
        uow.transactions.find_by_id.return_value = existing
        uow.transactions.update.return_value = _make_transaction(subcategory_id=None)
        dto = UpdateTransactionDTO(subcategory_id=None)

        await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        fields = uow.transactions.update.call_args.kwargs
        assert fields["subcategory_id"] is None
        assert fields["subcategory_name"] is None
        assert fields["categorization_tier"] == "manual"

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_by_id.return_value = None
        dto = UpdateTransactionDTO(amount=Decimal("75.00"))

        with pytest.raises(TransactionNotFoundException):
            await service.update_transaction(transaction_id=99, user_id=10, dto=dto)

    @pytest.mark.asyncio()
    async def test_no_op_when_empty_body(self) -> None:
        service, uow = _build_service()
        existing = _make_transaction()
        uow.transactions.find_by_id.return_value = existing
        dto = UpdateTransactionDTO()

        result = await service.update_transaction(transaction_id=1, user_id=10, dto=dto)

        uow.transactions.update.assert_not_awaited()
        uow.outbox.add.assert_not_awaited()
        uow.commit.assert_not_awaited()
        assert result.id == existing.id
        assert result.amount == existing.amount


class TestDeleteTransaction:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        tx = _make_transaction()
        uow.transactions.find_by_id.return_value = tx
        uow.transactions.delete.return_value = True

        await service.delete_transaction(transaction_id=1, user_id=10)

        uow.commit.assert_awaited_once()
        uow.outbox.add.assert_awaited_once()
        call_kwargs = uow.outbox.add.call_args[1]
        event = call_kwargs["event"]
        assert event.event_type == "transaction.deleted"
        assert event.transaction_id == 1

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_by_id.return_value = None

        with pytest.raises(TransactionNotFoundException):
            await service.delete_transaction(transaction_id=99, user_id=10)


class TestImportCSV:
    @pytest.mark.asyncio()
    async def test_success_uses_add_batch(self) -> None:
        service, uow = _build_service()
        tx = _make_transaction()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [tx]
        csv_content = (
            b"date,amount,transaction_type,account_id,account_name,"
            b"category_id,category_name,description\n"
            b"2026-03-01,49.99,expense,100,Main Account,5,Food,Groceries\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 1
        assert result.skipped == 0
        assert result.duplicates_skipped == 0
        assert result.errors == []
        uow.commit.assert_awaited_once()
        uow.outbox.add_batch.assert_awaited_once()
        batch_arg = uow.outbox.add_batch.call_args[0][0]
        assert len(batch_arg) == 1
        event, agg_type, agg_id = batch_arg[0]
        assert event.event_type == "transaction.created"
        assert agg_type == "transaction"

    @pytest.mark.asyncio()
    async def test_partial_failure(self) -> None:
        service, uow = _build_service()
        tx = _make_transaction()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [tx]
        csv_content = (
            b"date,amount,transaction_type,account_id,account_name\n"
            b"2026-03-01,49.99,expense,100,Main Account\n"
            b"2026-03-01,INVALID,expense,100,Main Account\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 1
        assert result.skipped == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio()
    async def test_duplicates_skipped(self) -> None:
        service, uow = _build_service()
        # The row's dedup key already exists in the DB (no description
        # column in this CSV -> description is None in the key).
        uow.transactions.find_existing_dedup_keys.return_value = {
            (100, date(2026, 3, 1), Decimal("49.99"), None),
        }
        csv_content = (
            b"date,amount,transaction_type,account_id,account_name\n2026-03-01,49.99,expense,100,Main Account\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 0
        assert result.duplicates_skipped == 1
        uow.transactions.bulk_create.assert_not_awaited()
        uow.outbox.add_batch.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_intra_file_duplicate_imported_once(self) -> None:
        """The same row twice in one file must import once and count the
        repeat as a skipped duplicate — even when the DB has no match."""
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction()]
        csv_content = (
            b"date,amount,transaction_type,account_id,account_name,"
            b"category_id,category_name,description\n"
            b"2026-03-01,49.99,expense,100,Main Account,5,Food,Groceries\n"
            b"2026-03-01,49.99,expense,100,Main Account,5,Food,Groceries\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 1
        assert result.duplicates_skipped == 1
        rows_arg = uow.transactions.bulk_create.call_args[0][0]
        assert len(rows_arg) == 1

    @pytest.mark.asyncio()
    async def test_dedup_uses_single_batch_query(self) -> None:
        """One anti-join query for the whole file — never one per row."""
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [
            _make_transaction(id=1),
            _make_transaction(id=2),
            _make_transaction(id=3),
        ]
        csv_content = (
            b"date,amount,transaction_type,account_id,account_name,"
            b"category_id,category_name,description\n"
            b"2026-03-01,49.99,expense,100,Main Account,5,Food,Netto\n"
            b"2026-03-02,12.50,expense,100,Main Account,5,Food,Kaffe\n"
            b"2026-03-03,7.00,expense,100,Main Account,5,Food,Kiosk\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 3
        uow.transactions.find_existing_dedup_keys.assert_awaited_once()
        _user_id, keys = uow.transactions.find_existing_dedup_keys.call_args[0]
        assert _user_id == 10
        assert keys == [
            (100, date(2026, 3, 1), Decimal("49.99"), "Netto"),
            (100, date(2026, 3, 2), Decimal("12.50"), "Kaffe"),
            (100, date(2026, 3, 3), Decimal("7.00"), "Kiosk"),
        ]

    @pytest.mark.asyncio()
    async def test_all_invalid_no_outbox(self) -> None:
        service, uow = _build_service()
        csv_content = (
            b"date,amount,transaction_type,account_id,account_name\n2026-03-01,INVALID,expense,100,Main Account\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 0
        assert result.skipped == 1
        uow.outbox.add_batch.assert_not_awaited()
        uow.commit.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_unknown_bank_format_raises(self) -> None:
        service, _uow = _build_service()

        with pytest.raises(CSVImportException, match="Unknown bank format"):
            await service.import_csv(
                user_id=10,
                csv_content=b"irrelevant",
                bank_format="unknown_bank",
                account_id=1,
                account_name="Test",
            )

    @pytest.mark.asyncio()
    async def test_non_internal_format_requires_account(self) -> None:
        service, _uow = _build_service()

        with pytest.raises(CSVImportException, match="account_id and account_name are required"):
            await service.import_csv(
                user_id=10,
                csv_content=b"irrelevant",
                bank_format="nordea",
            )


def _bulk_item(**overrides) -> BulkCreateTransactionItemDTO:  # type: ignore[no-untyped-def]
    defaults = {
        "account_id": 100,
        "account_name": "Main Account",
        "category_id": 5,
        "category_name": "Food",
        "amount": Decimal("49.99"),
        "transaction_type": TransactionType.EXPENSE,
        "description": "Groceries",
        "date": date(2026, 3, 1),
    }
    defaults.update(overrides)
    return BulkCreateTransactionItemDTO(**defaults)


class TestBulkImport:
    @pytest.mark.asyncio()
    async def test_all_new_items_imported(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [
            _make_transaction(id=1),
            _make_transaction(id=2),
        ]
        dto = BulkCreateTransactionDTO(
            items=[_bulk_item(description="Netto"), _bulk_item(description="Føtex")],
        )

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 2
        assert result.duplicates_skipped == 0
        assert result.errors == 0
        assert result.imported_ids == [1, 2]
        uow.commit.assert_awaited_once()
        uow.outbox.add_batch.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_duplicates_are_skipped(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = {
            (100, date(2026, 3, 1), Decimal("49.99"), "Netto"),
        }
        uow.transactions.bulk_create.return_value = [_make_transaction(id=3)]
        dto = BulkCreateTransactionDTO(
            items=[_bulk_item(description="Netto"), _bulk_item(description="Føtex")],
        )

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 1
        assert result.duplicates_skipped == 1
        assert result.errors == 0
        assert result.imported_ids == [3]

        bulk_arg = uow.transactions.bulk_create.call_args[0][0]
        assert len(bulk_arg) == 1
        assert bulk_arg[0]["description"] == "Føtex"

    @pytest.mark.asyncio()
    async def test_dedup_uses_single_batch_query(self) -> None:
        """One anti-join query for the whole payload — never per item."""
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [
            _make_transaction(id=1),
            _make_transaction(id=2),
        ]
        dto = BulkCreateTransactionDTO(
            items=[_bulk_item(description="Netto"), _bulk_item(description="Føtex")],
        )

        await service.bulk_import(user_id=10, dto=dto)

        uow.transactions.find_existing_dedup_keys.assert_awaited_once()
        _user_id, keys = uow.transactions.find_existing_dedup_keys.call_args[0]
        assert _user_id == 10
        assert keys == [
            (100, date(2026, 3, 1), Decimal("49.99"), "Netto"),
            (100, date(2026, 3, 1), Decimal("49.99"), "Føtex"),
        ]

    @pytest.mark.asyncio()
    async def test_intra_batch_duplicate_imported_once(self) -> None:
        """A key repeated within one payload imports once — the repeat
        counts as a skipped duplicate even with an empty DB."""
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction(id=1)]
        dto = BulkCreateTransactionDTO(items=[_bulk_item(), _bulk_item()])

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 1
        assert result.duplicates_skipped == 1
        bulk_arg = uow.transactions.bulk_create.call_args[0][0]
        assert len(bulk_arg) == 1

    @pytest.mark.asyncio()
    async def test_skip_duplicates_false_bypasses_lookup(self) -> None:
        service, uow = _build_service()
        uow.transactions.bulk_create.return_value = [
            _make_transaction(id=1),
            _make_transaction(id=2),
        ]
        # Identical items: with skip_duplicates=False even intra-batch
        # repeats must be imported verbatim.
        dto = BulkCreateTransactionDTO(items=[_bulk_item(), _bulk_item()], skip_duplicates=False)

        result = await service.bulk_import(user_id=10, dto=dto)

        uow.transactions.find_existing_dedup_keys.assert_not_awaited()
        uow.transactions.bulk_create.assert_awaited_once()
        assert result.duplicates_skipped == 0
        assert len(uow.transactions.bulk_create.call_args[0][0]) == 2

    @pytest.mark.asyncio()
    async def test_all_duplicates_still_commits(self) -> None:
        """If every item is a duplicate we still close the UoW cleanly
        without calling ``bulk_create`` or writing outbox events."""
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = {
            (100, date(2026, 3, 1), Decimal("49.99"), "Groceries"),
        }
        dto = BulkCreateTransactionDTO(items=[_bulk_item(), _bulk_item()])

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 0
        assert result.duplicates_skipped == 2
        uow.transactions.bulk_create.assert_not_awaited()
        uow.outbox.add_batch.assert_not_awaited()
        uow.commit.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_writes_outbox_events_with_new_fields(self) -> None:
        """Bulk-import outbox events must include tx_date,
        transaction_type and category_id — the enriched v1 payload
        consumed by TransactionSyncConsumer.
        """
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction()]
        dto = BulkCreateTransactionDTO(items=[_bulk_item()])

        await service.bulk_import(user_id=10, dto=dto)

        batch_arg = uow.outbox.add_batch.call_args[0][0]
        event, agg_type, agg_id = batch_arg[0]
        assert event.event_type == "transaction.created"
        assert event.transaction_type == "expense"
        assert event.tx_date == date(2026, 3, 1)
        assert event.category_id == 5
        assert event.user_id == 10

    @pytest.mark.asyncio()
    async def test_categorization_metadata_propagates_to_repo_and_event(self) -> None:
        """Tier/confidence/subcategory_id from the request reach both
        the persistence layer and the outbox event (tier-badge data
        round-trip all the way to the MySQL projection).
        """
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [
            _make_transaction(
                subcategory_id=77,
                categorization_tier="rule",
                categorization_confidence="high",
            ),
        ]
        dto = BulkCreateTransactionDTO(
            items=[
                _bulk_item(
                    subcategory_id=77,
                    categorization_tier="rule",
                    categorization_confidence="high",
                ),
            ],
        )

        await service.bulk_import(user_id=10, dto=dto)

        row = uow.transactions.bulk_create.call_args[0][0][0]
        assert row["subcategory_id"] == 77
        assert row["categorization_tier"] == "rule"
        assert row["categorization_confidence"] == "high"

        event, _, _ = uow.outbox.add_batch.call_args[0][0][0]
        assert event.subcategory_id == 77
        assert event.categorization_tier == "rule"
        assert event.categorization_confidence == "high"

    # ── P2-09: external_id-based dedup ──────────────────────────────

    @pytest.mark.asyncio()
    async def test_existing_external_id_is_skipped(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_existing_external_ids.return_value = {(100, "EB-1")}
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction(id=2, external_id="EB-2")]
        dto = BulkCreateTransactionDTO(
            items=[
                _bulk_item(description="Netto", external_id="EB-1"),
                _bulk_item(description="Føtex", external_id="EB-2"),
            ],
        )

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 1
        assert result.duplicates_skipped == 1
        bulk_arg = uow.transactions.bulk_create.call_args[0][0]
        assert [row["external_id"] for row in bulk_arg] == ["EB-2"]

    @pytest.mark.asyncio()
    async def test_legacy_fallback_skips_fuzzy_match_against_null_rows(self) -> None:
        """Transition: an id-bearing item whose fuzzy key matches a
        pre-P2-09 row (external_id IS NULL) is skipped — and the fuzzy
        lookup for id-bearing items must be scoped with
        only_missing_external_id=True."""
        service, uow = _build_service()
        uow.transactions.find_existing_external_ids.return_value = set()
        uow.transactions.find_existing_dedup_keys.return_value = {
            (100, date(2026, 3, 1), Decimal("49.99"), "Netto"),
        }
        dto = BulkCreateTransactionDTO(items=[_bulk_item(description="Netto", external_id="EB-1")])

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 0
        assert result.duplicates_skipped == 1
        uow.transactions.bulk_create.assert_not_awaited()
        assert uow.transactions.find_existing_dedup_keys.call_args.kwargs == {
            "only_missing_external_id": True,
        }

    @pytest.mark.asyncio()
    async def test_identical_fuzzy_key_with_different_external_id_imports(self) -> None:
        """H10 regression: two identical same-day purchases are distinct
        transactions when they carry distinct external_ids — a fuzzy
        match against an id-bearing row must NOT dedupe (the repo query
        is scoped to NULL rows, so it returns nothing here)."""
        service, uow = _build_service()
        uow.transactions.find_existing_external_ids.return_value = set()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction(id=9, external_id="EB-2")]
        dto = BulkCreateTransactionDTO(items=[_bulk_item(external_id="EB-2")])

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 1
        assert result.duplicates_skipped == 0

    @pytest.mark.asyncio()
    async def test_same_external_id_twice_in_payload_imports_once(self) -> None:
        """EB pagination can overlap — a repeated external_id within one
        payload must import once, or the whole flush would die on the
        partial unique index."""
        service, uow = _build_service()
        uow.transactions.find_existing_external_ids.return_value = set()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction(id=1, external_id="EB-1")]
        dto = BulkCreateTransactionDTO(
            items=[
                _bulk_item(description="Netto", external_id="EB-1"),
                _bulk_item(description="Netto (drift)", external_id="EB-1"),
            ],
        )

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 1
        assert result.duplicates_skipped == 1
        assert len(uow.transactions.bulk_create.call_args[0][0]) == 1

    @pytest.mark.asyncio()
    async def test_external_id_and_currency_reach_rows_and_events(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_existing_external_ids.return_value = set()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [
            _make_transaction(id=1, external_id="EB-1", currency="EUR"),
        ]
        dto = BulkCreateTransactionDTO(items=[_bulk_item(external_id="EB-1", currency="EUR")])

        await service.bulk_import(user_id=10, dto=dto)

        row = uow.transactions.bulk_create.call_args[0][0][0]
        assert row["external_id"] == "EB-1"
        assert row["currency"] == "EUR"

        event, _, _ = uow.outbox.add_batch.call_args[0][0][0]
        assert event.external_id == "EB-1"
        assert event.currency == "EUR"

    @pytest.mark.asyncio()
    async def test_items_without_external_id_never_query_external_ids(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction()]
        dto = BulkCreateTransactionDTO(items=[_bulk_item()])

        await service.bulk_import(user_id=10, dto=dto)

        uow.transactions.find_existing_external_ids.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_mixed_batch_queries_each_path_once(self) -> None:
        """One external-id lookup + one NULL-scoped fuzzy lookup for the
        id-bearing items, one plain fuzzy lookup for the rest — never
        per item."""
        service, uow = _build_service()
        uow.transactions.find_existing_external_ids.return_value = set()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [
            _make_transaction(id=1, external_id="EB-1"),
            _make_transaction(id=2),
        ]
        dto = BulkCreateTransactionDTO(
            items=[
                _bulk_item(description="Netto", external_id="EB-1"),
                _bulk_item(description="Føtex"),
            ],
        )

        result = await service.bulk_import(user_id=10, dto=dto)

        assert result.imported == 2
        uow.transactions.find_existing_external_ids.assert_awaited_once_with(10, [(100, "EB-1")])
        fuzzy_calls = uow.transactions.find_existing_dedup_keys.await_args_list
        assert len(fuzzy_calls) == 2
        scoped = [c for c in fuzzy_calls if c.kwargs.get("only_missing_external_id")]
        plain = [c for c in fuzzy_calls if not c.kwargs.get("only_missing_external_id")]
        assert len(scoped) == len(plain) == 1
        assert scoped[0].args[1] == [(100, date(2026, 3, 1), Decimal("49.99"), "Netto")]
        assert plain[0].args[1] == [(100, date(2026, 3, 1), Decimal("49.99"), "Føtex")]


class TestCreatePlanned:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        uow.planned.create.return_value = _make_planned()
        dto = CreatePlannedTransactionDTO(
            account_id=100,
            account_name="Main Account",
            category_id=5,
            category_name="Rent",
            amount=Decimal("5000.00"),
            transaction_type=TransactionType.EXPENSE,
            description="Monthly rent",
            recurrence="monthly",
            next_execution=date(2026, 4, 1),
        )

        result = await service.create_planned(user_id=10, dto=dto)

        uow.planned.create.assert_awaited_once()
        assert result.id == 1
        assert result.recurrence == "monthly"


class TestDeactivatePlanned:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, uow = _build_service()
        uow.planned.find_by_id.return_value = _make_planned()
        uow.planned.deactivate.return_value = True

        await service.deactivate_planned(planned_id=1, user_id=10)

        uow.planned.deactivate.assert_awaited_once_with(1, 10)

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, uow = _build_service()
        uow.planned.find_by_id.return_value = None

        with pytest.raises(PlannedTransactionNotFoundException):
            await service.deactivate_planned(planned_id=99, user_id=10)


class TestUoWRollback:
    @pytest.mark.asyncio()
    async def test_rollback_on_exception(self) -> None:
        service, uow = _build_service()
        uow.transactions.create.side_effect = RuntimeError("DB error")
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            amount=Decimal("10.00"),
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 3, 1),
        )

        with pytest.raises(RuntimeError, match="DB error"):
            await service.create_transaction(user_id=10, dto=dto)

        uow.commit.assert_not_awaited()
        uow.__aexit__.assert_awaited_once()
