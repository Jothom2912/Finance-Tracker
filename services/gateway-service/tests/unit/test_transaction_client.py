from __future__ import annotations

import logging
from datetime import date

import app.adapters.outbound.transaction_client as tc
from app.adapters.outbound.transaction_client import HttpAnalyticsReadRepository


def _row(tx_id: int, tx_date: str = "2026-06-02") -> dict:
    return {
        "id": tx_id,
        "amount": -10,
        "description": f"tx {tx_id}",
        "date": tx_date,
        "transaction_type": "expense",
        "category_id": None,
        "category_name": None,
        "subcategory_id": None,
        "subcategory_name": None,
        "account_id": 1,
        "categorization_tier": None,
    }


class _FakeResponse:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def raise_for_status(self) -> None:
        pass

    def json(self) -> list[dict]:
        return self._rows


class _FakeHttpxClient:
    """Serves one entry from `pages` per GET; repeats the last page if
    more GETs arrive (simulates an upstream that never runs dry)."""

    def __init__(self, pages: list[list[dict]], calls: list[dict]) -> None:
        self._pages = pages
        self._calls = calls

    def __enter__(self) -> _FakeHttpxClient:
        return self

    def __exit__(self, *args) -> bool:
        return False

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> _FakeResponse:
        index = len(self._calls)
        self._calls.append({"url": url, "params": params, "headers": headers})
        rows = self._pages[index] if index < len(self._pages) else self._pages[-1]
        return _FakeResponse(rows)


def _patch_httpx(monkeypatch, pages: list[list[dict]]) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr(tc.httpx, "Client", lambda timeout=None: _FakeHttpxClient(pages, calls))
    return calls


def test_sends_date_and_pagination_params(monkeypatch) -> None:
    calls = _patch_httpx(monkeypatch, [[_row(1)]])
    repo = HttpAnalyticsReadRepository("Bearer abc")

    result = repo.get_transactions(
        account_id=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert len(calls) == 1
    assert calls[0]["params"] == {
        "account_id": 1,
        "start_date": "2026-06-01",
        "end_date": "2026-06-30",
        "skip": 0,
        "limit": tc.TRANSACTION_PAGE_SIZE,
    }
    assert calls[0]["headers"] == {"Authorization": "Bearer abc"}
    assert [r["id"] for r in result] == [1]


def test_omits_date_params_when_not_provided(monkeypatch) -> None:
    calls = _patch_httpx(monkeypatch, [[]])
    HttpAnalyticsReadRepository("").get_transactions(account_id=7)

    assert "start_date" not in calls[0]["params"]
    assert "end_date" not in calls[0]["params"]
    assert calls[0]["params"]["account_id"] == 7


def test_paginates_until_short_page(monkeypatch) -> None:
    monkeypatch.setattr(tc, "TRANSACTION_PAGE_SIZE", 2)
    calls = _patch_httpx(monkeypatch, [[_row(1), _row(2)], [_row(3)]])

    result = HttpAnalyticsReadRepository("").get_transactions(account_id=1)

    assert len(calls) == 2
    assert [c["params"]["skip"] for c in calls] == [0, 2]
    assert all(c["params"]["limit"] == 2 for c in calls)
    assert [r["id"] for r in result] == [1, 2, 3]


def test_pagination_stops_at_page_cap_with_warning(monkeypatch, caplog) -> None:
    monkeypatch.setattr(tc, "TRANSACTION_PAGE_SIZE", 2)
    monkeypatch.setattr(tc, "MAX_TRANSACTION_PAGES", 3)
    # Every page is full, so only the cap stops the loop.
    calls = _patch_httpx(monkeypatch, [[_row(1), _row(2)]])

    with caplog.at_level(logging.WARNING):
        result = HttpAnalyticsReadRepository("").get_transactions(account_id=1)

    assert len(calls) == 3
    assert len(result) == 6
    assert any("page cap" in record.message for record in caplog.records)


def test_client_side_date_filter_is_kept_as_safety_net(monkeypatch) -> None:
    """Even if upstream ignores the date params, rows outside the range
    must still be filtered out locally."""
    _patch_httpx(
        monkeypatch,
        [[_row(1, "2026-05-31"), _row(2, "2026-06-15"), _row(3, "2026-07-01")]],
    )

    result = HttpAnalyticsReadRepository("").get_transactions(
        account_id=1,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 30),
    )

    assert [r["id"] for r in result] == [2]
