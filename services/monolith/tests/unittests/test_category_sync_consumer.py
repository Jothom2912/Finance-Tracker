from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.consumers.category_sync import CategorySyncConsumer
from backend.models.mysql.category import Category as CategoryModel


def _make_consumer(
    session_factory: MagicMock | None = None,
) -> CategorySyncConsumer:
    return CategorySyncConsumer(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        db_session_factory=session_factory or MagicMock(),
    )


def _category_created_event(
    category_id: int = 99,
    name: str = "TestCategory",
    category_type: str = "expense",
    correlation_id: str = "corr-cat-001",
) -> dict:
    return {
        "event_type": "category.created",
        "event_version": 1,
        "category_id": category_id,
        "name": name,
        "category_type": category_type,
        "correlation_id": correlation_id,
        "timestamp": "2026-04-23T00:00:00+00:00",
    }


class TestCategorySyncCreated:
    @pytest.mark.asyncio()
    async def test_new_category_gets_display_order_after_max(self) -> None:
        """A newly synced category should get display_order = max + 1."""
        session = MagicMock()

        filter_mock = MagicMock()
        filter_mock.first.return_value = None

        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        query_mock.scalar.return_value = 15

        session.query.return_value = query_mock

        factory = MagicMock(return_value=session)
        consumer = _make_consumer(factory)

        await consumer.handle(_category_created_event(category_id=50, name="Ny Kategori"))

        session.add.assert_called_once()
        added_model = session.add.call_args[0][0]
        assert added_model.display_order == 16
        session.commit.assert_called_once()

    @pytest.mark.asyncio()
    async def test_first_category_gets_display_order_1(self) -> None:
        """When the table is empty, COALESCE returns 0, so first gets 1."""
        session = MagicMock()

        filter_mock = MagicMock()
        filter_mock.first.return_value = None

        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        query_mock.scalar.return_value = 0

        session.query.return_value = query_mock

        factory = MagicMock(return_value=session)
        consumer = _make_consumer(factory)

        await consumer.handle(_category_created_event(category_id=1, name="First"))

        added_model = session.add.call_args[0][0]
        assert added_model.display_order == 1

    @pytest.mark.asyncio()
    async def test_skips_existing_category(self) -> None:
        session = MagicMock()
        existing = MagicMock()

        query_mock = MagicMock()
        query_mock.filter.return_value.first.return_value = existing

        session.query.return_value = query_mock

        factory = MagicMock(return_value=session)
        consumer = _make_consumer(factory)

        await consumer.handle(_category_created_event(category_id=5))

        session.add.assert_not_called()
        session.commit.assert_not_called()

    @pytest.mark.asyncio()
    async def test_rollback_on_error(self) -> None:
        session = MagicMock()

        filter_mock = MagicMock()
        filter_mock.first.return_value = None

        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        query_mock.scalar.return_value = 0
        session.query.return_value = query_mock
        session.commit.side_effect = RuntimeError("DB error")

        factory = MagicMock(return_value=session)
        consumer = _make_consumer(factory)

        with pytest.raises(RuntimeError, match="DB error"):
            await consumer.handle(_category_created_event())

        session.rollback.assert_called_once()
        session.close.assert_called_once()

    @pytest.mark.asyncio()
    async def test_always_closes_session(self) -> None:
        session = MagicMock()

        filter_mock = MagicMock()
        filter_mock.first.return_value = None

        query_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        query_mock.scalar.return_value = 5
        session.query.return_value = query_mock

        factory = MagicMock(return_value=session)
        consumer = _make_consumer(factory)

        await consumer.handle(_category_created_event())

        session.close.assert_called_once()
