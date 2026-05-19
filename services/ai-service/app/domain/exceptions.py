"""Domain exceptions for analytics data retrieval.

Mapped from HTTP status codes in the analytics adapter so the pipeline can
emit typed ErrorEvents without coupling to httpx or HTTP semantics.
"""

from __future__ import annotations


class AnalyticsError(Exception):
    """Base class for analytics data retrieval failures."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AnalyticsAuthError(AnalyticsError):
    """Token expired or insufficient permissions (HTTP 401/403)."""


class AnalyticsNotFoundError(AnalyticsError):
    """Requested resource does not exist (HTTP 404)."""


class AnalyticsServiceUnavailableError(AnalyticsError):
    """Backend service is down or overloaded (HTTP 5xx)."""
