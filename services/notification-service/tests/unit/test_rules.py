"""Unit tests for the notification-firing predicates."""

from __future__ import annotations

import pytest
from app.domain.rules import should_notify_bank_sync
from contracts.events.bank import SyncTrigger


@pytest.mark.parametrize(
    ("new_imported", "errors"),
    [(0, 0), (5, 0), (0, 3), (5, 3)],
)
def test_manual_sync_always_notifies(new_imported: int, errors: int) -> None:
    # The user pressed a button; "nothing changed" is still an answer they are
    # owed. Silence on a manual sync reads as a failure.
    assert should_notify_bank_sync(trigger=SyncTrigger.MANUAL, new_imported=new_imported, errors=errors)


def test_scheduled_sync_with_nothing_to_report_is_silent() -> None:
    assert not should_notify_bank_sync(trigger=SyncTrigger.SCHEDULED, new_imported=0, errors=0)


def test_scheduled_sync_with_imports_notifies() -> None:
    assert should_notify_bank_sync(trigger=SyncTrigger.SCHEDULED, new_imported=1, errors=0)


def test_scheduled_sync_with_only_errors_notifies() -> None:
    # Nothing imported but something went wrong — that is exactly the case the
    # user cannot discover on their own, so it must not be swallowed.
    assert should_notify_bank_sync(trigger=SyncTrigger.SCHEDULED, new_imported=0, errors=2)
