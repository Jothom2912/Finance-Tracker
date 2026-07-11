"""JWT decoding shared by every service that consumes finans-tracker tokens.

This module only *validates and decodes* tokens. It intentionally does not
mint tokens — see the package README for why token minting is not part of
this package.
"""

from __future__ import annotations

from typing import Any, Sequence

from jose import JWTError, jwt

DEFAULT_ALGORITHMS: tuple[str, ...] = ("HS256",)


class InvalidTokenError(Exception):
    """Raised when a token cannot be decoded, is expired/malformed, or lacks
    a usable identity claim (``user_id`` or ``sub``).
    """


def decode_token(
    token: str,
    secret: str,
    algorithms: Sequence[str] = DEFAULT_ALGORITHMS,
    require_exp: bool = False,
) -> dict[str, Any]:
    """Decode ``token`` and return its claims.

    The returned claims dict always has a ``user_id`` key normalized to an
    ``int``, taken from either a ``user_id`` claim (issued by most services)
    or a ``sub`` claim (issued by user-service and the saga/account-service
    style issuers). All other claims are passed through unchanged.

    Args:
        token: The raw JWT string (without the ``Bearer `` prefix).
        secret: The shared HMAC secret used to verify the signature.
        algorithms: Allowed signing algorithms. Defaults to ``["HS256"]``,
            matching every service's current configuration.
        require_exp: If ``True``, a token without an ``exp`` claim is
            rejected. Defaults to ``False`` to preserve the current
            behavior of every service (none of them currently require
            tokens to carry an expiry). Services that want to enforce
            expiry on all tokens should opt in explicitly — see the
            package README.

    Raises:
        InvalidTokenError: If the signature is invalid, the token is
            malformed, it has expired (when it does carry an ``exp``
            claim), ``require_exp`` is set and ``exp`` is missing, or
            neither ``user_id`` nor ``sub`` resolves to an integer.
    """
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=list(algorithms),
            options={"require_exp": require_exp},
        )
    except JWTError as exc:
        raise InvalidTokenError(f"Could not validate token: {exc}") from exc

    raw_user_id = claims.get("user_id")
    if raw_user_id is None:
        sub = claims.get("sub")
        if sub is None:
            raise InvalidTokenError("Token is missing a 'user_id' or 'sub' claim")
        raw_user_id = sub

    try:
        claims["user_id"] = int(raw_user_id)
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError(
            f"Token identity claim is not a valid integer: {raw_user_id!r}"
        ) from exc

    return claims
