"""Pure predicates deciding *whether* a trigger event becomes a notification.

Separate from :mod:`app.domain.messages`, which decides what a notification
*says*. Both are clock-free, I/O-free and take primitives — the wire format is
the application layer's problem, so nothing here imports the event contracts
(cf. the hexagonal rule that domain has no infrastructure dependencies).
"""

from __future__ import annotations


def should_notify_bank_sync(*, scheduled: bool, new_imported: int, errors: int, parse_skipped: int = 0) -> bool:
    """False only for a scheduled sync that had nothing to report.

    F1-05's nightly scheduler runs every active connection through the same
    saga as the manual button, so without this rule every user gets one
    "ingen nye transaktioner" notification per connection per night — the
    fastest way to make someone mute the bell.

    A *manual* sync always notifies, including when nothing was imported:
    the user pressed a button and is owed an answer, and "nothing changed" is
    an answer. Silence there would read as a failure.

    "Nothing to report" means all three counters are zero. ``parse_skipped``
    matters as much as ``errors``: a sync that fetched 40 transactions and
    could not read one of them has ``new_imported == 0`` and ``errors == 0``,
    but it is broken, not quiet. Suppressing it would make a dead bank
    connection indistinguishable from a healthy night.
    """
    if not scheduled:
        return True
    return new_imported > 0 or errors > 0 or parse_skipped > 0
