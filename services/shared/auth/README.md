# finans-tracker-auth

Shared JWT decoding and a FastAPI dependency for authenticating requests
across services. Every microservice currently carries its own near-identical
copy of `app/auth.py`; this package consolidates the decoding logic and the
`get_current_user_id` dependency that all of them ultimately implement.

## What this package does NOT do

**It does not mint tokens.** Only user-service should issue access tokens
(via its own login endpoint). budget-service's `make_service_auth_header`
helper — which mints a short-lived JWT for service-to-service HTTP calls —
is a known antipattern tracked separately as **backlog P3-02** and is
intentionally **not** included here. Do not add a `create_access_token` /
`make_service_auth_header` equivalent to this package without first
resolving P3-02; doing so would just relocate the antipattern instead of
fixing it.

This package also does not do password hashing. `hash_password` /
`verify_password` (found today in user-service and, unused, in
account-service) belong to the service that owns user credentials
(user-service), not to a shared auth-decoding library.

## Install

```bash
uv add --editable ../shared/auth/
```

or, in `pyproject.toml`:

```toml
dependencies = [
    "finans-tracker-auth",
]

[tool.uv.sources]
finans-tracker-auth = { path = "../shared/auth" }
```

## Usage

### Decoding a token directly

```python
from auth.jwt import decode_token, InvalidTokenError

try:
    claims = decode_token(token, secret="...", algorithms=["HS256"])
except InvalidTokenError:
    ...  # reject the request

user_id: int = claims["user_id"]  # normalized from `user_id` or `sub`
```

`decode_token` accepts either a `user_id` claim (used by most services'
issuers) or a `sub` claim (used by user-service/saga-service/account-service
style issuers) and normalizes whichever is present into an integer
`claims["user_id"]`. A non-numeric identity claim raises `InvalidTokenError`
with a message naming the offending value, instead of propagating a raw
`ValueError`/`TypeError`.

`require_exp` defaults to `False`, matching every service's behavior today:
none of them currently require a token to carry an `exp` claim (a token
without `exp` is accepted; a token *with* an expired `exp` is still
rejected). Services that want to start enforcing expiry on every token
should pass `require_exp=True` explicitly — this is an opt-in behavior
change, not a default, precisely so adopting this package does not silently
tighten or loosen any service's current auth behavior.

### FastAPI dependency

```python
from auth.fastapi import make_current_user_dependency
from app.config import settings

get_current_user_id = make_current_user_dependency(lambda: settings.JWT_SECRET)

@router.get("/me")
def me(user_id: int = Depends(get_current_user_id)):
    ...
```

The secret is supplied via a zero-argument callable (`SecretProvider`)
rather than a plain string so each service keeps resolving it from its own
`Settings` object — including services/tests that patch or reload settings
at runtime.

The dependency reproduces the three-message 401 flow used today by
banking-service, saga-service and account-service (the most complete of the
several slightly-diverging copies found across the 9 services):

| Condition | Status | `detail` |
|---|---|---|
| No `Authorization` header | 401 | `Missing authentication token` |
| Header present but not `Bearer <token>` (wrong scheme, missing token, extra parts) | 401 | `Invalid authentication format. Use: Bearer <token>` |
| Header well-formed but token fails to decode/validate (bad signature, expired, unparsable, non-numeric identity claim) | 401 | `Invalid or expired authentication token` |

All three responses carry `WWW-Authenticate: Bearer`.

Some services' existing copies use slightly different wording or a
different transport (`OAuth2PasswordBearer`, `HTTPBearer`, or gateway's
custom `httpx`-based verification that omits `WWW-Authenticate` entirely).
Adopting this package is a small behavior change for those services — see
`MIGRATION.md`.

## Architecture

```text
auth/
├── jwt.py      # decode_token, InvalidTokenError
└── fastapi.py  # make_current_user_dependency
```

## Testing

```bash
cd services/shared/auth
uv sync --extra dev
uv run pytest
```
