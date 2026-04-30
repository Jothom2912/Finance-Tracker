"""Unit tests for the CategorizationClient (HTTP client to categorization-service).

Tests the graceful degradation behavior when categorization-service
is unavailable or slow.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.adapters.outbound.categorization_client import CategorizationClient


@pytest.fixture()
def client() -> CategorizationClient:
    return CategorizationClient()


class TestGracefulDegradation:
    async def test_returns_none_on_timeout(self, client: CategorizationClient) -> None:
        import httpx

        with patch("app.adapters.outbound.categorization_client.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post.side_effect = httpx.TimeoutException("timeout")
            mock_cls.return_value = mock_instance

            result = await client.categorize("Netto Nordhavn", -150.0)
            assert result is None

    async def test_returns_none_on_connection_error(self, client: CategorizationClient) -> None:
        import httpx

        with patch("app.adapters.outbound.categorization_client.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post.side_effect = httpx.ConnectError("connection refused")
            mock_cls.return_value = mock_instance

            result = await client.categorize("Netto Nordhavn", -150.0)
            assert result is None

    async def test_batch_returns_nones_on_failure(self, client: CategorizationClient) -> None:
        import httpx

        with patch("app.adapters.outbound.categorization_client.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post.side_effect = httpx.ConnectError("connection refused")
            mock_cls.return_value = mock_instance

            items = [
                {"description": "Netto", "amount": -100.0},
                {"description": "DSB", "amount": -89.0},
            ]
            results = await client.categorize_batch(items)
            assert results == [None, None]
