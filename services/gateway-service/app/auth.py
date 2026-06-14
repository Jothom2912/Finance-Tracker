from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.config import (
    ACCOUNT_SERVICE_TIMEOUT,
    ACCOUNT_SERVICE_URL,
    JWT_ALGORITHM,
    SECRET_KEY,
)

logger = logging.getLogger(__name__)


def _decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            sub = payload.get("sub")
            if sub is None:
                return None
            user_id = int(sub)
        return user_id
    except (JWTError, ValueError, TypeError):
        return None


def get_user_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    token = authorization[len("Bearer ") :]
    user_id = _decode_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user_id


def get_account_id_from_headers(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_account_id: Optional[str] = Header(None, alias="X-Account-ID"),
) -> Optional[int]:
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer "):]

    if x_account_id:
        try:
            account_id = int(x_account_id)
        except ValueError:
            return None

        if token:
            user_id = _decode_token(token)
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
        user_id = _decode_token(token)
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
