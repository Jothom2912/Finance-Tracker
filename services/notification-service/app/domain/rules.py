"""Pure predicates deciding *whether* a trigger event becomes a notification.

Separate from :mod:`app.domain.messages`, which decides what a notification
*says*. Both are clock-free and I/O-free so every branch is unit-testable
without a UoW.
"""

from __future__ import annotations

from contracts.events.bank import SyncTrigger


def should_notify_bank_sync(*, trigger: SyncTrigger, new_imported: int, errors: int) -> bool:
    """False only for a scheduled sync that had nothing to report.

    F1-05's nightly scheduler runs every active connection through the same
    saga as the manual button, so without this rule every user gets one
    "ingen nye transaktioner" notification per connection per night — the
    fastest way to make someone mute the bell.

    A *manual* sync always notifies, including when nothing was imported:
    the user pressed a button and is owed an answer, and "nothing changed" is
    an answer. Silence there would read as a failure.
    """
    if trigger is not SyncTrigger.SCHEDULED:
        return True
    return new_imported > 0 or errors > 0
