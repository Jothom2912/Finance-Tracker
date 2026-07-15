from __future__ import annotations

import os

import httpx
import pytest

_HEALTH_ENDPOINTS = [
    "http://localhost:8001/health",
    "http://localhost:8002/health",
    "http://localhost:8003/health",
    "http://localhost:8004/health",
    "http://localhost:8006/health",
    "http://localhost:8010/health",
]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip e2e tests when services are not reachable.

    In CI (``CI`` env var set, as GitHub Actions always does) unreachable
    services abort the run with a failure instead: an all-skipped suite exits
    0 and would make the e2e job green without running a single test.
    """
    reachable = _services_reachable()
    if reachable:
        return

    if os.environ.get("CI"):
        pytest.exit(
            "docker-compose services not reachable - refusing to skip e2e tests in CI",
            returncode=1,
        )

    skip_marker = pytest.mark.skip(reason="docker-compose services not reachable")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_marker)


def _services_reachable() -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            return all(client.get(url).status_code == 200 for url in _HEALTH_ENDPOINTS)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return False
