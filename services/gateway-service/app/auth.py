"""Gateway auth: shared JWT validation + gateway-specific account resolution.

Core token decoding and the current-user dependency come from the shared
``finans-tracker-auth`` package. What stays local is deliberately
gateway-specific: ``get_account_id_from_headers`` resolves and
ownership-verifies an account id against account-service over HTTP.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from auth.fastapi import make_current_user_dependency
from auth.jwt import InvalidTokenError, decode_token
from fastapi import Header

from app.config import (
    ACCOUNT_SERVICE_TIMEOUT,
    ACCOUNT_SERVICE_URL,
    JWT_ALGORITHM,
    SECRET_KEY,
)

logger = logging.getLogger(__name__)

# Shared three-message 401 flow (Missing token / Invalid format / Invalid or
# expired token, all with WWW-Authenticate: Bearer). Routers keep importing
# this name — zero router changes.
get_user_id_from_headers = make_current_user_dependency(lambda: SECRET_KEY, algorithms=(JWT_ALGORITHM,))


def _decode_user_id(token: str) -> Optional[int]:
    """Best-effort user id from a raw token; ``None`` on any failure.

    ``get_account_id_from_headers`` is an *optional* auth path (it returns
    ``None`` rather than raising 401), so the shared ``InvalidTokenError``
    is translated back to ``None`` here.
    """
    try:
        return int(decode_token(token, SECRET_KEY, algorithms=(JWT_ALGORITHM,))["user_id"])
    except InvalidTokenError:
        return None


def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
) -> Optional[int]:
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :]

    if x_account_id:
        try:
            account_id = int(x_account_id)
        except ValueError:
            return None

        if token:
            user_id = _decode_user_id(token)
            if user_id is None:
                return None
            try:
                resp = httpx.get(
                    f"{ACCOUNT_SERVICE_URL}/api/v1/accounts/{account_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=ACCOUNT_SERVICE_TIMEOUT,
                )
                if resp.status_code == 200:
                    return account_id
            except Exception:
                logger.exception("Account ownership verification failed")
            return None
        return None

    if token:
        user_id = _decode_user_id(token)
        if user_id is None:
            return None
        try:
            resp = httpx.get(
                f"{ACCOUNT_SERVICE_URL}/api/v1/accounts",
                headers={"Authorization": f"Bearer {token}"},
                timeout=ACCOUNT_SERVICE_TIMEOUT,
            )
            if resp.status_code == 200:
                accounts = resp.json()
                if accounts:
                    return int(accounts[0].get("idAccount") or accounts[0].get("id"))
        except Exception:
            logger.exception("Account lookup for user failed")
        return None

    return None
