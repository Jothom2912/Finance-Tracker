from __future__ import annotations

from uuid import UUID


class BankingDomainException(Exception):
    pass


class BankConnectionNotFound(BankingDomainException):
    def __init__(self, connection_id: UUID) -> None:
        super().__init__(f"Bank connection {connection_id} not found")
        self.connection_id = connection_id


class BankConnectionInactive(BankingDomainException):
    def __init__(self, connection_id: UUID, status: str) -> None:
        super().__init__(
            f"Bank connection {connection_id} is not active (status={status})"
        )
        self.connection_id = connection_id
        self.status = status


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
