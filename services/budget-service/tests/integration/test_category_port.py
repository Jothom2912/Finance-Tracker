"""Integration tests for CategoryPort HTTP adapter.

Tester at CategoryPort:
1. Returnerer True når category-service svarer 200
2. Returnerer False når category-service svarer 404
3. Returnerer True (fail-open) når category-service er nede / timeout

Bruger respx til at mocke HTTP-kald uden rigtig service.
Kræver IKKE Docker.
"""

from __future__ import annotations

import os

import pytest
import respx
from httpx import Response

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dummy/dummy")
os.environ.setdefault("JWT_SECRET", "test-secret")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def category_port():
    from app.adapters.outbound.category_port import CategoryPort
    return CategoryPort()


# ---------------------------------------------------------------------------
# Tests: Kategori eksisterer
# ---------------------------------------------------------------------------

class TestCategoryExists:
    @respx.mock
    async def test_returns_true_when_service_responds_200(self, category_port) -> None:
        respx.get("http://localhost:8005/api/v1/categories/1").mock(return_value=Response(200))

        result = await category_port.exists(1)

        assert result is True

    @respx.mock
    async def test_returns_false_when_service_responds_404(self, category_port) -> None:
        respx.get("http://localhost:8005/api/v1/categories/99").mock(return_value=Response(404))

        result = await category_port.exists(99)

        assert result is False

    @respx.mock
    async def test_returns_false_when_service_responds_500(self, category_port) -> None:
        respx.get("http://localhost:8005/api/v1/categories/1").mock(return_value=Response(500))

        result = await category_port.exists(1)

        assert result is False


# ---------------------------------------------------------------------------
# Tests: Fail-open (service nede)
# ---------------------------------------------------------------------------

class TestCategoryPortFailOpen:
    @respx.mock
    async def test_returns_true_when_service_is_unreachable(self, category_port) -> None:
        """Når category-service er nede, skal vi fail-open (True) for ikke at blokere budgets."""
        import httpx
        respx.get("http://localhost:8005/api/v1/categories/5").mock(side_effect=httpx.ConnectError("Connection refused"))

        result = await category_port.exists(5)

        assert result is True

    @respx.mock
    async def test_returns_true_on_timeout(self, category_port) -> None:
        import httpx
        respx.get("http://localhost:8005/api/v1/categories/7").mock(side_effect=httpx.TimeoutException("Timeout"))

        result = await category_port.exists(7)

        assert result is True


# ---------------------------------------------------------------------------
# Tests: Korrekt URL bygges
# ---------------------------------------------------------------------------

class TestCategoryPortUrl:
    @respx.mock
    async def test_calls_correct_url_for_category_id(self, category_port) -> None:
        route = respx.get("http://localhost:8005/api/v1/categories/42").mock(return_value=Response(200))

        await category_port.exists(42)

        assert route.called
        assert route.call_count == 1
