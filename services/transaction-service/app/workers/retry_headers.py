"""Reading the ``x-retry-count`` header without trusting its shape.

aio-pika types a header value as a union of everything AMQP can carry —
``bytes | bytearray | Decimal | FieldArray | FieldTable | float | int | str |
datetime | None`` — because the wire format decides, not us. Every writer in this
repo sets an int, and AMQP round-trips ints as ints, so the union is wider than
what we produce. That is exactly why reading it loosely was safe-looking and
still wrong:

* ``saga_command_consumer`` special-cased ``bytes`` and then compared the raw
  value to an int. On a ``str`` header that raises ``TypeError``.
* ``categorized_consumer`` called ``int(...)``, which handles ``str`` and
  ``bytes`` but raises on ``None`` and on a non-numeric string.

Both reads live *inside* an ``except Exception`` retry handler, so an exception
there means the message is neither acked nor republished — it gets redelivered
forever with the counter never advancing. A poison-message loop is a worse
failure than the one being handled.

So anything that is not a usable count is treated as ``0``, i.e. "first
attempt": the retry ladder then advances normally and terminates at
``MAX_RETRIES`` instead of spinning. See
``dev-notes/findings/2026-07-27-retry-header-read-five-ways.md``.
"""

from __future__ import annotations

from decimal import Decimal

from aio_pika.abc import AbstractIncomingMessage

RETRY_HEADER = "x-retry-count"


def retry_count(message: AbstractIncomingMessage, header: str = RETRY_HEADER) -> int:
    """The message's retry count, or 0 if it has none we can use."""
    raw = (message.headers or {}).get(header, 0)
    if isinstance(raw, bool):
        # bool is an int subclass; a True here would silently mean "1 attempt".
        return 0
    if isinstance(raw, int):
        return raw
    # Decimal is in aio-pika's union and converts cleanly; listing it explicitly
    # beats a bare try/int on the container shapes below.
    if isinstance(raw, (float, Decimal, bytes, bytearray, str)):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    return 0
