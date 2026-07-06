"""Domain exceptions med eksplicit HTTP-mapping i adapter-laget.

Mapping (rest_api.py): AccountNotFoundError -> 404,
InvalidPeriodError -> 400, ReadStoreUnavailableError -> 503 + WARNING.
"""

from __future__ import annotations


class AnalyticsDomainError(Exception):
    """Base for alle domain-fejl i analytics-service."""


class AccountNotFoundError(AnalyticsDomainError):
    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        super().__init__(f"Konto {account_id} blev ikke fundet.")


class InvalidPeriodError(AnalyticsDomainError):
    def __init__(self, message: str = "Startdato kan ikke være efter slutdato.") -> None:
        super().__init__(message)


class ReadStoreUnavailableError(AnalyticsDomainError):
    def __init__(self, message: str = "Analytics-læselageret er utilgængeligt.") -> None:
        super().__init__(message)
