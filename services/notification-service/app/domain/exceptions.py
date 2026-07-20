"""Domain exceptions with explicit HTTP/consumer mapping in the adapter layer.

- ``NotificationNotFound`` → 404 in the API.
- ``AccountNotFound`` → the owning account is genuinely gone; the consumer
  drops the notification (nothing to deliver to), no retry.
- ``AccountOwnerUnavailable`` → account-service is down/unreachable; the
  consumer must let the message retry/DLQ, never silently drop it.
"""

from __future__ import annotations


class NotificationNotFound(Exception):
    def __init__(self, notification_id: str) -> None:
        super().__init__(f"Notification {notification_id} not found")


class AccountNotFound(Exception):
    def __init__(self, account_id: int) -> None:
        super().__init__(f"Account {account_id} not found")


class AccountOwnerUnavailable(Exception):
    def __init__(self) -> None:
        super().__init__("account-service is unavailable")
