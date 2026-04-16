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
from app.domain.entities import PlannedTransaction, Transaction, TransactionType
from app.domain.exceptions import (
    PlannedTransactionNotFoundException,
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
        uow.transactions.find_by_date_range.return_value = [_make_transaction()]
        filters = TransactionFiltersDTO(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

        results = await service.list_transactions(user_id=10, filters=filters)

        uow.transactions.find_by_date_range.assert_awaited_once_with(10, date(2026, 1, 1), date(2026, 12, 31))
        assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_with_account_filter(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_by_account.return_value = [_make_transaction()]
        filters = TransactionFiltersDTO(account_id=100)

        results = await service.list_transactions(user_id=10, filters=filters)

        uow.transactions.find_by_account.assert_awaited_once_with(100, 10)
        assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_default_pagination(self) -> None:
        service, uow = _build_service()
        uow.transactions.find_by_user.return_value = []
        filters = TransactionFiltersDTO()

        await service.list_transactions(user_id=10, filters=filters)

        uow.transactions.find_by_user.assert_awaited_once_with(10, skip=0, limit=50)


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
            amount=Decimal("49.99"), category_name="Food",
        )
        updated = _make_transaction(
            amount=Decimal("75.00"), category_name="Transport",
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
        uow.transactions.bulk_create.return_value = [tx]
        csv_content = (
            "date,amount,transaction_type,account_id,account_name,"
            "category_id,category_name,description\n"
            "2026-03-01,49.99,expense,100,Main Account,5,Food,Groceries\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 1
        assert result.skipped == 0
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
        uow.transactions.bulk_create.return_value = [tx]
        csv_content = (
            "date,amount,transaction_type,account_id,account_name\n"
            "2026-03-01,49.99,expense,100,Main Account\n"
            "2026-03-01,INVALID,expense,100,Main Account\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 1
        assert result.skipped == 1
        assert len(result.errors) == 1

    @pytest.mark.asyncio()
    async def test_all_invalid_no_outbox(self) -> None:
        service, uow = _build_service()
        csv_content = (
            "date,amount,transaction_type,account_id,account_name\n2026-03-01,INVALID,expense,100,Main Account\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 0
        assert result.skipped == 1
        uow.outbox.add_batch.assert_not_awaited()
        uow.commit.assert_not_awaited()


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
        uow.transactions.find_duplicate.return_value = None
        uow.transactions.bulk_create.return_value = [
            _make_transaction(id=1),
            _make_transaction(id=2),
        ]
        dto = BulkCreateTransactionDTO(items=[_bulk_item(), _bulk_item()])

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
        uow.transactions.find_duplicate.side_effect = [
            _make_transaction(id=99),
            None,
        ]
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
    async def test_skip_duplicates_false_bypasses_lookup(self) -> None:
        service, uow = _build_service()
        uow.transactions.bulk_create.return_value = [_make_transaction()]
        dto = BulkCreateTransactionDTO(items=[_bulk_item()], skip_duplicates=False)

        await service.bulk_import(user_id=10, dto=dto)

        uow.transactions.find_duplicate.assert_not_awaited()
        uow.transactions.bulk_create.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_all_duplicates_still_commits(self) -> None:
        """If every item is a duplicate we still close the UoW cleanly
        without calling ``bulk_create`` or writing outbox events."""
        service, uow = _build_service()
        uow.transactions.find_duplicate.return_value = _make_transaction()
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
        uow.transactions.find_duplicate.return_value = None
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
