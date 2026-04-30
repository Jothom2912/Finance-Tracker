"""Domain exceptions for the banking context.

These are intentional business-rule violations raised by
``BankingService`` so the presentation layer can map each to the
right HTTP status code.  Anything *not* in this hierarchy is a bug —
callers must let it propagate to FastAPI's default 500 handler rather
than absorb it silently.
"""

from __future__ import annotations


class BankingError(Exception):
    """Base class for all banking-domain exceptions.

    Catching this type is equivalent to "known banking business-rule
    violation" — distinct from adapter I/O errors (e.g.
    ``TransactionServiceError``) or generic Python failures.
    """


class BankConnectionNotFound(BankingError):
    """The referenced ``BankConnection`` row does not exist.

    Maps to HTTP 404 — the caller referenced an identifier that is
    not present in our projection.
    """

    def __init__(self, connection_id: int) -> None:
        self.connection_id = connection_id
        super().__init__(f"Bank connection {connection_id} not found")


class BankConnectionInactive(BankingError):
    """The connection exists but is not in a syncable state.

    Maps to HTTP 409 (Conflict) — the resource exists but the current
    state forbids the requested operation.  Frontend can react
    differently than for 404 (e.g. show a "reconnect bank" CTA).
    """

    def __init__(self, connection_id: int, status: str) -> None:
        self.connection_id = connection_id
        self.status = status
        super().__init__(f"Bank connection {connection_id} is {status}")


class BankAccountReferenceInvalid(BankingError):
    """Internal invariant breach — a ``BankConnection.account_id`` does
    not point to an existing ``Account`` row.

    Maps to HTTP 500 — this is an integrity failure in our own data,
    never something the caller can fix.  Kept distinct from "not
    found" so monitoring can alert on it specifically.
    """

    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        super().__init__(f"Bank connection points to non-existent account {account_id}")
