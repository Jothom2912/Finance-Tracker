"""Domain exceptions with explicit HTTP/consumer mapping in the adapter layer.

- ``NotificationNotFound`` → 404 in the API.
- ``AccountNotFound`` → the owning account is genuinely gone; the consumer
  drops the notification (nothing to deliver to), no retry.
- ``AccountOwnerUnavailable`` → account-service is down/unreachable; the
  consumer must let the message retry/DLQ, never silently drop it.
- ``AccountOwnerAuthError`` → account-service answered, but rejected *us*
  (401/403). Same retry/DLQ handling as unavailable, but kept distinct so a
  bad ``INTERNAL_API_KEY`` does not read as an upstream outage in the logs.
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


class AccountOwnerAuthError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"account-service rejected the internal API key (HTTP {status_code})")
