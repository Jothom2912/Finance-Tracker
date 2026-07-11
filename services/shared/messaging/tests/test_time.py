from __future__ import annotations

from datetime import timedelta, timezone

from messaging.time import utcnow, utcnow_naive


def test_utcnow_is_timezone_aware() -> None:
    now = utcnow()
    assert now.tzinfo is timezone.utc


def test_utcnow_naive_is_naive_utc() -> None:
    naive = utcnow_naive()
    aware = utcnow()
    assert naive.tzinfo is None
    delta = aware.replace(tzinfo=None) - naive
    assert abs(delta) < timedelta(seconds=2)
