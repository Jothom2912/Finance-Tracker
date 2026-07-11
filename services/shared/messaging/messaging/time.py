"""Time helpers shared by outbox and consumer code.

Every service currently stores outbox timestamps in naive
``TIMESTAMP WITHOUT TIME ZONE`` columns, populated with
``datetime.now(timezone.utc).replace(tzinfo=None)`` scattered across
copies.  These two helpers centralise that convention.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """UTC now as timezone-naive datetime.

    Matches the naive ``DateTime`` columns services currently use
    (``TIMESTAMP WITHOUT TIME ZONE`` filled with UTC wall-clock time).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
