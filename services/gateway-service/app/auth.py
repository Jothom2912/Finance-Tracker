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
get_user_id_from_headers = make_current_user_dependency(
    lambda: SECRET_KEY,
    algorithms=(JWT_ALGORITHM,),
    require_exp=True,
)


def _decode_user_id(token: str) -> Optional[int]:
    """Best-effort user id from a raw token; ``None`` on any failure.

    ``get_account_id_from_headers`` is an *optional* auth path (it returns
    ``None`` rather than raising 401), so the shared ``InvalidTokenError``
    is translated back to ``None`` here.
    """
    try:
        return int(decode_token(token, SECRET_KEY, algorithms=(JWT_ALGORITHM,), require_exp=True)["user_id"])
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
            # Trailing slash er påkrævet: account-service ruter
            # ``/api/v1/accounts/``, og uden slash svarer FastAPI 307, som
            # httpx ikke følger by default. Denne sti returnerede derfor
            # altid None — se findings/2026-07-27-gateway-default-account-307.
            resp = httpx.get(
                f"{ACCOUNT_SERVICE_URL}/api/v1/accounts/",
                headers={"Authorization": f"Bearer {token}"},
                timeout=ACCOUNT_SERVICE_TIMEOUT,
            )
            if resp.status_code == 200:
                accounts = resp.json()
                # EKSPLICIT valg, ikke ``accounts[0]`` (P2-40). Listesvaret har
                # ingen ``ORDER BY`` (account-service
                # postgresql_account_repository.py:23), så "første konto" er
                # heap-orden — for en flerkonto-bruger uden ``X-Account-ID`` var
                # svaret dermed en anden kontos tal, præsenteret som den valgte,
                # og uden en fejl. Målt: 1554,00 kr. fra den forkerte konto.
                # Standardkontoen er derimod en regel repoet allerede har:
                # account_creation_consumer opretter ``name="Default Account"``,
                # og migration 002 har det partielle unique index
                # ``one_default_per_user`` netop på det navn. Findes den ikke,
                # returneres None, og ``_require_account_id`` giver den ærlige
                # fejl frem for et gæt.
                default = next((a for a in accounts if a.get("name") == "Default Account"), None)
                if default is not None:
                    return int(default.get("idAccount") or default.get("id"))
                logger.warning(
                    "No 'Default Account' for user %s and no X-Account-ID sent; "
                    "resolving to None (P2-40). Accounts found: %d",
                    user_id,
                    len(accounts),
                )
        except Exception:
            logger.exception("Account lookup for user failed")
        return None

    return None
