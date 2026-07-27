"""``retry_count`` must never raise — the callers are retry handlers.

Both call sites read ``x-retry-count`` from inside an ``except Exception`` block.
An exception there means the message is neither acked nor republished, so the
broker redelivers it forever with the counter never advancing: a poison loop that
is worse than the error being handled. That is what the two previous spellings
did on a ``str`` (saga: ``TypeError``) and on ``None``/non-numeric (categorized:
``TypeError``/``ValueError``).

See dev-notes/findings/2026-07-27-retry-header-read-five-ways.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from app.workers.retry_headers import retry_count


class _Message:
    """Just the one attribute ``retry_count`` touches."""

    def __init__(self, headers: dict[str, Any] | None) -> None:
        self.headers = headers


@pytest.mark.parametrize(
    ("headers", "expected", "case"),
    [
        # Shapes our own writers produce — these must keep working exactly.
        ({}, 0, "header absent"),
        (None, 0, "no headers at all"),
        ({"x-retry-count": 0}, 0, "int zero"),
        ({"x-retry-count": 3}, 3, "int"),
        # Shapes AMQP may hand back that the old reads mishandled.
        ({"x-retry-count": "3"}, 3, "str — saga raised TypeError here"),
        ({"x-retry-count": b"3"}, 3, "bytes"),
        ({"x-retry-count": bytearray(b"3")}, 3, "bytearray"),
        ({"x-retry-count": 3.0}, 3, "float"),
        ({"x-retry-count": Decimal("3")}, 3, "Decimal"),
        # Unusable — 0 means "first attempt", so the ladder advances and ends.
        ({"x-retry-count": None}, 0, "explicit null"),
        ({"x-retry-count": "abc"}, 0, "non-numeric str"),
        ({"x-retry-count": [1]}, 0, "list"),
        ({"x-retry-count": {"a": 1}}, 0, "dict"),
        ({"x-retry-count": datetime(2026, 1, 1, tzinfo=timezone.utc)}, 0, "datetime"),
    ],
)
def test_retry_count_coerces_or_falls_back_to_zero(
    headers: dict[str, Any] | None,
    expected: int,
    case: str,
) -> None:
    assert retry_count(_Message(headers)) == expected, case  # type: ignore[arg-type]


def test_retry_count_does_not_read_true_as_one() -> None:
    """bool is an int subclass, so a True header would silently mean 1 attempt."""
    assert retry_count(_Message({"x-retry-count": True})) == 0  # type: ignore[arg-type]


def test_retry_count_honours_a_custom_header_name() -> None:
    assert retry_count(_Message({"x-other": 2}), header="x-other") == 2  # type: ignore[arg-type]
