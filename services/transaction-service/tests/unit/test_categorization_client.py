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

            result = await client.categorize("Netto Nordhavn", -150.0, "outgoing")
            assert result is None

    async def test_returns_none_on_connection_error(self, client: CategorizationClient) -> None:
        import httpx

        with patch("app.adapters.outbound.categorization_client.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post.side_effect = httpx.ConnectError("connection refused")
            mock_cls.return_value = mock_instance

            result = await client.categorize("Netto Nordhavn", -150.0, "outgoing")
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
                {"description": "Netto", "amount": -100.0, "direction": "outgoing"},
                {"description": "DSB", "amount": -89.0, "direction": "outgoing"},
            ]
            results = await client.categorize_batch(items)
            assert results == [None, None]


class TestInternalApiKeyHeader:
    """The sync path is S2S-only (P1-15); both endpoints must carry the key.

    Asserted on the outgoing call rather than end-to-end because the
    server-side enforcement lives in categorization-service — if this
    header silently disappeared, the client would degrade to ``None``
    and transactions would quietly stop getting a category.
    """

    @staticmethod
    def _mock_client() -> AsyncMock:
        import httpx

        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.post.side_effect = httpx.ConnectError("connection refused")
        return mock_instance

    async def test_single_sends_configured_key(self) -> None:
        with patch("app.adapters.outbound.categorization_client.settings") as mock_settings:
            mock_settings.CATEGORIZATION_SERVICE_URL = "http://categorization:8005"
            mock_settings.CATEGORIZATION_TIMEOUT_S = 0.5
            mock_settings.INTERNAL_API_KEY = "s3cret"
            client = CategorizationClient()

        with patch("app.adapters.outbound.categorization_client.httpx.AsyncClient") as mock_cls:
            mock_instance = self._mock_client()
            mock_cls.return_value = mock_instance
            await client.categorize("Netto", -100.0, "outgoing")

        assert mock_instance.post.await_args.kwargs["headers"] == {"X-Internal-API-Key": "s3cret"}

    async def test_batch_sends_configured_key(self) -> None:
        with patch("app.adapters.outbound.categorization_client.settings") as mock_settings:
            mock_settings.CATEGORIZATION_SERVICE_URL = "http://categorization:8005"
            mock_settings.CATEGORIZATION_TIMEOUT_S = 0.5
            mock_settings.INTERNAL_API_KEY = "s3cret"
            client = CategorizationClient()

        with patch("app.adapters.outbound.categorization_client.httpx.AsyncClient") as mock_cls:
            mock_instance = self._mock_client()
            mock_cls.return_value = mock_instance
            await client.categorize_batch([{"description": "Netto", "amount": -100.0, "direction": "outgoing"}])

        assert mock_instance.post.await_args.kwargs["headers"] == {"X-Internal-API-Key": "s3cret"}

    async def test_unconfigured_key_sends_no_header(self) -> None:
        """Keeps A1 harmless on its own: an unset key must not send an
        empty header value that A2 would then reject."""
        with patch("app.adapters.outbound.categorization_client.settings") as mock_settings:
            mock_settings.CATEGORIZATION_SERVICE_URL = "http://categorization:8005"
            mock_settings.CATEGORIZATION_TIMEOUT_S = 0.5
            mock_settings.INTERNAL_API_KEY = None
            client = CategorizationClient()

        with patch("app.adapters.outbound.categorization_client.httpx.AsyncClient") as mock_cls:
            mock_instance = self._mock_client()
            mock_cls.return_value = mock_instance
            await client.categorize("Netto", -100.0, "outgoing")

        assert mock_instance.post.await_args.kwargs["headers"] == {}
