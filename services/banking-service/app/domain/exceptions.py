from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID


class BankingDomainException(Exception):
    pass


class BankConnectionNotFound(BankingDomainException):
    def __init__(self, connection_id: UUID) -> None:
        super().__init__(f"Bank connection {connection_id} not found")
        self.connection_id = connection_id


class BankConnectionInactive(BankingDomainException):
    def __init__(self, connection_id: UUID, status: str) -> None:
        super().__init__(f"Bank connection {connection_id} is not active (status={status})")
        self.connection_id = connection_id
        self.status = status


class BankConsentExpired(BankingDomainException):
    """The Enable Banking consent (valid_until) has lapsed.

    Distinct from BankConnectionInactive: the connection row is still
    'active', but the bank-side consent window has closed — the user
    must re-authorize (reconsent) before syncs can run. Mapped to 409
    in the adapter layer with a Danish reconsent hint.
    """

    def __init__(self, connection_id: UUID, expires_at: Optional[datetime]) -> None:
        super().__init__(f"Bank consent for connection {connection_id} expired at {expires_at}")
        self.connection_id = connection_id
        self.expires_at = expires_at


class BankAccountNotOwned(BankingDomainException):
    """User referenced an account_id they don't own or that doesn't exist."""

    def __init__(self, account_id: int) -> None:
        super().__init__(f"Account {account_id} not accessible")
        self.account_id = account_id


class ProjectionIntegrityError(BankingDomainException):
    """account_id should exist in accounts_projection but doesn't.

    Unlike BankAccountNotOwned (authorization — the user's fault), this
    signals an internal inconsistency: a bank_connection references an
    account_id that the projection has lost track of.  The distinction
    matters for HTTP mapping (403 vs 500) and for log severity (WARNING
    vs ERROR with stacktrace).
    """

    def __init__(self, account_id: int) -> None:
        super().__init__(f"Account {account_id} missing from projection — internal inconsistency")
        self.account_id = account_id


class PendingAuthorizationNotFound(BankingDomainException):
    def __init__(self, state: str) -> None:
        super().__init__(f"No pending authorization for state={state}")
        self.state = state
