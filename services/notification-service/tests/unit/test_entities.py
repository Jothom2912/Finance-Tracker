from __future__ import annotations

from datetime import datetime, timezone

from app.domain.entities import Notification, NotificationContent, NotificationType


def _content() -> NotificationContent:
    return NotificationContent(
        type=NotificationType.GOAL_REACHED,
        title="Mål nået! 🎉",
        body="Du har nået dit sparemål.",
    )


def test_from_content_copies_type_and_text() -> None:
    n = Notification.from_content(user_id=7, content=_content(), source_key="goal.reached:1")
    assert n.user_id == 7
    assert n.type is NotificationType.GOAL_REACHED
    assert n.title == "Mål nået! 🎉"
    assert n.source_key == "goal.reached:1"
    assert n.id is None


def test_is_read_is_computed_from_timestamp() -> None:
    n = Notification.from_content(user_id=1, content=_content(), source_key="k")
    assert n.is_read is False
    n.read_at = datetime(2026, 7, 20, tzinfo=timezone.utc)
    assert n.is_read is True


def test_is_dismissed_is_computed_from_timestamp() -> None:
    n = Notification.from_content(user_id=1, content=_content(), source_key="k")
    assert n.is_dismissed is False
    n.dismissed_at = datetime(2026, 7, 20, tzinfo=timezone.utc)
    assert n.is_dismissed is True
