"""UUIDv7 generation (RFC 9562).

New primary keys in this codebase are UUIDv7 (CLAUDE.md): time-ordered so
inserts stay roughly sequential on the index, without leaking an
auto-increment count across services. Python 3.11 has no ``uuid.uuid7``
(added in 3.14) and the repo pulls in no uuid7 dependency, so we generate
it here.

Layout (128 bits):
    48 bits  unix timestamp in milliseconds
     4 bits  version (0b0111 = 7)
    12 bits  rand_a (random)
     2 bits  variant (0b10)
    62 bits  rand_b (random)

``timestamp_ms`` is injectable so the pure part is deterministic in tests
(CLAUDE.md: no ``datetime.now()`` buried in logic). Reading the clock is
left to the default, which callers at the infra boundary use.
"""

from __future__ import annotations

import os
import time
from uuid import UUID

_MASK_48 = (1 << 48) - 1
_MASK_12 = (1 << 12) - 1
_MASK_62 = (1 << 62) - 1


def uuid7(timestamp_ms: int | None = None) -> UUID:
    """Return a UUIDv7. Pass ``timestamp_ms`` to make it deterministic."""
    if timestamp_ms is None:
        timestamp_ms = time.time_ns() // 1_000_000

    ts = timestamp_ms & _MASK_48
    rand_a = int.from_bytes(os.urandom(2), "big") & _MASK_12
    rand_b = int.from_bytes(os.urandom(8), "big") & _MASK_62

    value = (ts << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return UUID(int=value)
