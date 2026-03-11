from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, call

import pytest

from app.application.dto import (
    CreatePlannedTransactionDTO,
    CreateTransactionDTO,
    TransactionFiltersDTO,
)
from app.application.service import TransactionService
from app.domain.entities import PlannedTransaction, Transaction, TransactionType
from app.domain.exceptions import (
    CSVImportException,
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
    tx_repo = AsyncMock()
    planned_repo = AsyncMock()
    uow = AsyncMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    publisher = AsyncMock()

    service = TransactionService(
        transaction_repo=tx_repo,
        planned_repo=planned_repo,
        uow=uow,
        event_publisher=publisher,
    )
    return service, tx_repo, planned_repo, uow, publisher


class TestCreateTransaction:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, tx_repo, _, uow, _ = _build_service()
        tx = _make_transaction()
        tx_repo.create.return_value = tx
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

        tx_repo.create.assert_awaited_once()
        uow.commit.assert_awaited_once()
        assert result.id == 1
        assert result.amount == Decimal("49.99")
        assert result.account_name == "Main Account"

    @pytest.mark.asyncio()
    async def test_publishes_event(self) -> None:
        service, tx_repo, _, _, publisher = _build_service()
        tx_repo.create.return_value = _make_transaction()
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 3, 1),
        )

        await service.create_transaction(user_id=10, dto=dto)

        publisher.publish.assert_awaited_once()
        event = publisher.publish.call_args[0][0]
        assert event.event_type == "transaction.created"
        assert event.transaction_id == 1
        assert event.user_id == 10
        assert event.amount == "49.99"

    @pytest.mark.asyncio()
    async def test_event_after_commit(self) -> None:
        service, tx_repo, _, uow, publisher = _build_service()
        tx_repo.create.return_value = _make_transaction()
        call_order: list[str] = []
        uow.commit.side_effect = lambda: call_order.append("commit")
        publisher.publish.side_effect = lambda e: call_order.append("publish")
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            amount=Decimal("49.99"),
            transaction_type=TransactionType.EXPENSE,
            date=date(2026, 3, 1),
        )

        await service.create_transaction(user_id=10, dto=dto)

        assert call_order == ["commit", "publish"]


class TestGetTransaction:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, tx_repo, _, _, _ = _build_service()
        tx_repo.find_by_id.return_value = _make_transaction()

        result = await service.get_transaction(transaction_id=1, user_id=10)

        assert result.id == 1
        tx_repo.find_by_id.assert_awaited_once_with(1, 10)

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, tx_repo, _, _, _ = _build_service()
        tx_repo.find_by_id.return_value = None

        with pytest.raises(TransactionNotFoundException):
            await service.get_transaction(transaction_id=99, user_id=10)


class TestListTransactions:
    @pytest.mark.asyncio()
    async def test_with_date_filter(self) -> None:
        service, tx_repo, _, _, _ = _build_service()
        tx_repo.find_by_date_range.return_value = [_make_transaction()]
        filters = TransactionFiltersDTO(
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

        results = await service.list_transactions(user_id=10, filters=filters)

        tx_repo.find_by_date_range.assert_awaited_once_with(
            10, date(2026, 1, 1), date(2026, 12, 31)
        )
        assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_with_account_filter(self) -> None:
        service, tx_repo, _, _, _ = _build_service()
        tx_repo.find_by_account.return_value = [_make_transaction()]
        filters = TransactionFiltersDTO(account_id=100)

        results = await service.list_transactions(user_id=10, filters=filters)

        tx_repo.find_by_account.assert_awaited_once_with(100, 10)
        assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_default_pagination(self) -> None:
        service, tx_repo, _, _, _ = _build_service()
        tx_repo.find_by_user.return_value = []
        filters = TransactionFiltersDTO()

        await service.list_transactions(user_id=10, filters=filters)

        tx_repo.find_by_user.assert_awaited_once_with(10, skip=0, limit=50)


class TestDeleteTransaction:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, tx_repo, _, uow, publisher = _build_service()
        tx = _make_transaction()
        tx_repo.find_by_id.return_value = tx
        tx_repo.delete.return_value = True

        await service.delete_transaction(transaction_id=1, user_id=10)

        uow.commit.assert_awaited_once()
        publisher.publish.assert_awaited_once()
        event = publisher.publish.call_args[0][0]
        assert event.event_type == "transaction.deleted"
        assert event.transaction_id == 1

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, tx_repo, _, _, _ = _build_service()
        tx_repo.find_by_id.return_value = None

        with pytest.raises(TransactionNotFoundException):
            await service.delete_transaction(transaction_id=99, user_id=10)


class TestImportCSV:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, tx_repo, _, uow, publisher = _build_service()
        tx = _make_transaction()
        tx_repo.bulk_create.return_value = [tx]
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
        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_partial_failure(self) -> None:
        service, tx_repo, _, uow, _ = _build_service()
        tx = _make_transaction()
        tx_repo.bulk_create.return_value = [tx]
        csv_content = (
            "date,amount,transaction_type,account_id,account_name\n"
            "2026-03-01,49.99,expense,100,Main Account\n"
            "2026-03-01,INVALID,expense,100,Main Account\n"
        )

        result = await service.import_csv(user_id=10, csv_content=csv_content)

        assert result.imported == 1
        assert result.skipped == 1
        assert len(result.errors) == 1


class TestCreatePlanned:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, _, planned_repo, _, _ = _build_service()
        planned_repo.create.return_value = _make_planned()
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

        planned_repo.create.assert_awaited_once()
        assert result.id == 1
        assert result.recurrence == "monthly"


class TestDeactivatePlanned:
    @pytest.mark.asyncio()
    async def test_success(self) -> None:
        service, _, planned_repo, _, _ = _build_service()
        planned_repo.find_by_id.return_value = _make_planned()
        planned_repo.deactivate.return_value = True

        await service.deactivate_planned(planned_id=1, user_id=10)

        planned_repo.deactivate.assert_awaited_once_with(1, 10)

    @pytest.mark.asyncio()
    async def test_not_found(self) -> None:
        service, _, planned_repo, _, _ = _build_service()
        planned_repo.find_by_id.return_value = None

        with pytest.raises(PlannedTransactionNotFoundException):
            await service.deactivate_planned(planned_id=99, user_id=10)


class TestUoWRollback:
    @pytest.mark.asyncio()
    async def test_rollback_on_exception(self) -> None:
        service, tx_repo, _, uow, _ = _build_service()
        tx_repo.create.side_effect = RuntimeError("DB error")
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
