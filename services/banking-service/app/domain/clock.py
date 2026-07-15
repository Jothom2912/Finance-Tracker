"""Injectable clock for the domain/application layer.

Convention (see CLAUDE.md): no ``datetime.now()``/``datetime.utcnow()``
directly in domain or application logic — inject a ``Clock`` callable so
tests stay deterministic. The default produces timezone-aware UTC;
adapters that persist to the naive ``TIMESTAMP WITHOUT TIME ZONE``
columns strip tzinfo at the persistence boundary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    """Timezone-aware UTC now (default production clock)."""
    return datetime.now(timezone.utc)
