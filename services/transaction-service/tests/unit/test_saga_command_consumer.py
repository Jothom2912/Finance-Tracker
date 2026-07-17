from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.application.dto import BulkCreateResultDTO
from app.domain.exceptions import TransactionNotFoundException
from app.workers.saga_command_consumer import TransactionSagaCommandConsumer


async def _run_bulk_import(
    items: list[dict],
    *,
    results: list[BulkCreateResultDTO] | None = None,
) -> tuple[AsyncMock, dict]:
    """Drive _handle_bulk_import with mocked persistence; return the
    service mock (to inspect received DTOs) and the reply dict.
    ``results`` provides one BulkCreateResultDTO per expected chunk."""
    consumer = TransactionSagaCommandConsumer()
    mock_service = AsyncMock()
    if results is not None:
        mock_service.bulk_import.side_effect = results
    else:
        mock_service.bulk_import.return_value = BulkCreateResultDTO(
            imported=len(items),
            duplicates_skipped=0,
            errors=0,
            imported_ids=list(range(1, len(items) + 1)),
        )

    with (
        patch("app.workers.saga_command_consumer.async_session_factory") as session_factory,
        patch("app.workers.saga_command_consumer.SQLAlchemyUnitOfWork"),
        patch("app.workers.saga_command_consumer.TransactionService", return_value=mock_service),
    ):
        session_factory.return_value.__aenter__.return_value = MagicMock()
        reply = await consumer._handle_bulk_import(
            {
                "user_id": 10,
                "account_id": 100,
                "account_name": "Main Account",
                "items": items,
            },
        )
    return mock_service, reply


@pytest.mark.asyncio
async def test_bulk_import_maps_external_id_and_currency_to_dto() -> None:
    service, _ = await _run_bulk_import(
        [
            {
                "amount": "49.99",
                "transaction_type": "expense",
                "date": "2026-03-01",
                "description": "Netto",
                "external_id": "EB-REF-1",
                "currency": "EUR",
            },
        ],
    )

    dto = service.bulk_import.await_args.kwargs["dto"]
    item = dto.items[0]
    assert item.account_id == 100
    assert item.amount == Decimal("49.99")
    assert item.date == date(2026, 3, 1)
    assert item.external_id == "EB-REF-1"
    assert item.currency == "EUR"


@pytest.mark.asyncio
async def test_bulk_import_normalizes_blank_or_missing_external_id() -> None:
    """ ""/null/whitespace external_ids must map to None (never a dedup
    key) and missing currency defaults to DKK — old in-flight messages
    keep the pure fuzzy path."""
    service, _ = await _run_bulk_import(
        [
            {"amount": "1.00", "transaction_type": "expense", "date": "2026-03-01", "description": "a"},
            {
                "amount": "2.00",
                "transaction_type": "expense",
                "date": "2026-03-01",
                "description": "b",
                "external_id": "",
                "currency": None,
            },
            {
                "amount": "3.00",
                "transaction_type": "expense",
                "date": "2026-03-01",
                "description": "c",
                "external_id": "   ",
            },
        ],
    )

    dto = service.bulk_import.await_args.kwargs["dto"]
    assert [item.external_id for item in dto.items] == [None, None, None]
    assert [item.currency for item in dto.items] == ["DKK", "DKK", "DKK"]


@pytest.mark.asyncio
async def test_bulk_import_zero_items_replies_success_without_touching_db() -> None:
    """An EB fetch with nothing new must reply success (0 imported) —
    not trip the DTO's min_length=1 and fail the saga (P3-15)."""
    consumer = TransactionSagaCommandConsumer()

    with patch("app.workers.saga_command_consumer.async_session_factory") as session_factory:
        reply = await consumer._handle_bulk_import(
            {"user_id": 10, "account_id": 100, "account_name": "Main Account", "items": []},
        )

    session_factory.assert_not_called()
    assert reply == {
        "success": True,
        "result_data": {"imported": 0, "duplicates_skipped": 0, "errors": 0, "imported_ids": []},
    }


@pytest.mark.asyncio
async def test_bulk_import_chunks_batches_beyond_dto_max_and_aggregates() -> None:
    """1001 items must become 500+500+1 bulk_import calls (the DTO caps
    items per call) with counts and imported_ids aggregated across
    chunks in order — an oversize EB fetch must not ValidationError the
    saga (P3-15)."""
    items = [
        {
            "amount": "1.00",
            "transaction_type": "expense",
            "date": "2026-03-01",
            "description": f"tx-{i}",
            "external_id": f"EB-{i}",
        }
        for i in range(1001)
    ]
    results = [
        BulkCreateResultDTO(imported=499, duplicates_skipped=1, errors=0, imported_ids=list(range(1, 500))),
        BulkCreateResultDTO(imported=500, duplicates_skipped=0, errors=0, imported_ids=list(range(500, 1000))),
        BulkCreateResultDTO(imported=0, duplicates_skipped=1, errors=0, imported_ids=[]),
    ]
    service, reply = await _run_bulk_import(items, results=results)

    chunk_sizes = [len(call.kwargs["dto"].items) for call in service.bulk_import.await_args_list]
    assert chunk_sizes == [500, 500, 1]
    # Chunk order preserved: the first item of chunk 2 is item 500.
    assert service.bulk_import.await_args_list[1].kwargs["dto"].items[0].external_id == "EB-500"
    assert reply["result_data"]["imported"] == 999
    assert reply["result_data"]["duplicates_skipped"] == 2
    assert reply["result_data"]["errors"] == 0
    assert reply["result_data"]["imported_ids"] == list(range(1, 1000))


@pytest.mark.asyncio
async def test_rollback_import_deletes_each_transaction() -> None:
    consumer = TransactionSagaCommandConsumer()
    mock_service = AsyncMock()
    mock_session = AsyncMock()

    with (
        patch("app.workers.saga_command_consumer.async_session_factory") as session_factory,
        patch("app.workers.saga_command_consumer.SQLAlchemyUnitOfWork"),
        patch("app.workers.saga_command_consumer.TransactionService", return_value=mock_service),
    ):
        session_factory.return_value.__aenter__.return_value = mock_session
        result = await consumer._handle_rollback_import(
            {"user_id": 10, "transaction_ids": [101, 102, 103]},
        )

    assert result == {"success": True, "is_compensation": True}
    assert mock_service.delete_transaction.await_count == 3
    mock_service.delete_transaction.assert_any_await(101, 10)
    mock_service.delete_transaction.assert_any_await(102, 10)
    mock_service.delete_transaction.assert_any_await(103, 10)


@pytest.mark.asyncio
async def test_rollback_import_noop_when_no_transaction_ids() -> None:
    consumer = TransactionSagaCommandConsumer()

    with patch("app.workers.saga_command_consumer.async_session_factory") as session_factory:
        result = await consumer._handle_rollback_import({"user_id": 10, "transaction_ids": []})

    session_factory.assert_not_called()
    assert result == {"success": True, "is_compensation": True}


@pytest.mark.asyncio
async def test_rollback_import_reports_failure_when_single_delete_fails() -> None:
    """A real delete failure must not be swallowed: all ids are still
    attempted, but the reply is success=False naming the failed id so
    the orchestrator can escalate the broken compensation."""
    consumer = TransactionSagaCommandConsumer()
    mock_service = AsyncMock()
    mock_service.delete_transaction.side_effect = [None, RuntimeError("DB down"), None]

    with (
        patch("app.workers.saga_command_consumer.async_session_factory") as session_factory,
        patch("app.workers.saga_command_consumer.SQLAlchemyUnitOfWork"),
        patch("app.workers.saga_command_consumer.TransactionService", return_value=mock_service),
    ):
        session_factory.return_value.__aenter__.return_value = MagicMock()
        result = await consumer._handle_rollback_import(
            {"user_id": 10, "transaction_ids": [1, 2, 3]},
        )

    assert result["success"] is False
    assert result["is_compensation"] is True
    assert "2" in result["error_message"]
    assert mock_service.delete_transaction.await_count == 3


@pytest.mark.asyncio
async def test_rollback_import_treats_already_deleted_as_success() -> None:
    """Missing transactions mean the compensation goal is already met —
    a redelivered rollback command must stay idempotent (success=True)."""
    consumer = TransactionSagaCommandConsumer()
    mock_service = AsyncMock()
    mock_service.delete_transaction.side_effect = [
        None,
        TransactionNotFoundException(2),
        TransactionNotFoundException(3),
    ]

    with (
        patch("app.workers.saga_command_consumer.async_session_factory") as session_factory,
        patch("app.workers.saga_command_consumer.SQLAlchemyUnitOfWork"),
        patch("app.workers.saga_command_consumer.TransactionService", return_value=mock_service),
    ):
        session_factory.return_value.__aenter__.return_value = MagicMock()
        result = await consumer._handle_rollback_import(
            {"user_id": 10, "transaction_ids": [1, 2, 3]},
        )

    assert result == {"success": True, "is_compensation": True}
    assert mock_service.delete_transaction.await_count == 3
