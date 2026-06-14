from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.workers.saga_command_consumer import TransactionSagaCommandConsumer


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
async def test_rollback_import_continues_when_single_delete_fails() -> None:
    consumer = TransactionSagaCommandConsumer()
    mock_service = AsyncMock()
    mock_service.delete_transaction.side_effect = [None, RuntimeError("not found"), None]

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
