"""
FastAPI dependency factory for auth-related ports.

Isolated module to avoid circular imports between auth.py and dependencies.py.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Header

import backend.config as config
from backend.shared.adapters.http_account_resolver import HttpAccountResolver
from backend.shared.ports.auth_ports import IAccountResolver


def get_account_resolver(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> IAccountResolver:
    """Create IAccountResolver for auth account resolution.

    Uses account-service HTTP API directly to avoid async MySQL sync delays.
    """
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]
    return HttpAccountResolver(
        token=token,
        base_url=config.ACCOUNT_SERVICE_URL,
        timeout=config.ACCOUNT_SERVICE_TIMEOUT,
    )
