from __future__ import annotations

import httpx
import pytest

_HEALTH_ENDPOINTS = [
    "http://localhost:8000/health",
    "http://localhost:8001/health",
    "http://localhost:8002/health",
]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip e2e tests when services are not reachable."""
    reachable = _services_reachable()
    if reachable:
        return

    skip_marker = pytest.mark.skip(
        reason="docker-compose services not reachable"
    )
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_marker)


def _services_reachable() -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            return all(
                client.get(url).status_code == 200
                for url in _HEALTH_ENDPOINTS
            )
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return False
