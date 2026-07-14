# Adopting finans-tracker-auth in a service

A mechanical, per-service recipe. The mechanics copy the already-adopted
`finans-tracker-contracts` pattern exactly (reference:
`services/goal-service/pyproject.toml` + `Dockerfile`).

## 1. pyproject.toml

```toml
[project]
dependencies = [
    # ...existing...
    "finans-tracker-auth",
]

[tool.uv.sources]
finans-tracker-auth = { path = "../shared/auth" }
```

Then, from the service directory:

```bash
uv lock
uv sync
```

The lock records `source = { directory = "../shared/auth" }`. uv does
not content-hash directory sources, so later shared-package edits do
not invalidate the lockfile; re-run `uv lock` only if the shared
package gains new third-party deps.

Package deps (`python-jose[cryptography]`, `fastapi`) are already in
every service — resolution should not change pins. Services that only
kept `python-jose` for their local auth copy can drop it from their own
dependency list after adoption (it arrives transitively).

## 2. Dockerfile

Add before the `uv sync --frozen` layer:

```dockerfile
COPY services/shared/auth /shared/auth
COPY services/<svc>/pyproject.toml services/<svc>/uv.lock ./
RUN uv sync --frozen --no-dev
```

`WORKDIR` is `/app`, so the recorded relative path `../shared/auth`
resolves to `/shared/auth` in the container — same relative layout as
on the host.

**Build-context caveat:** `COPY services/shared/...` requires the
repo-root build context (`context: .` in docker-compose.yml). Never
build with the service directory as context.

## 3. Import swap

| Old (service-local `app/auth.py`) | New (shared) |
|---|---|
| `def get_current_user_id(authorization: Optional[str] = Header(...))` (banking/saga/account style) | `get_current_user_id = make_current_user_dependency(lambda: settings.JWT_SECRET)` — `from auth.fastapi import make_current_user_dependency` |
| inline `jwt.decode(...)` + `user_id`/`sub` normalization | `from auth.jwt import decode_token, InvalidTokenError` — `decode_token(token, secret, algorithms=("HS256",), require_exp=False)` returns claims with `claims["user_id"]: int` |
| `decode_token(token) -> Optional[TokenData]` returning `None` on failure | `decode_token` **raises** `InvalidTokenError` instead of returning `None` — update callers that check for `None` |

Entry points:

```python
# auth.jwt
decode_token(token: str, secret: str,
             algorithms: Sequence[str] = ("HS256",),
             require_exp: bool = False) -> dict[str, Any]   # raises InvalidTokenError
class InvalidTokenError(Exception)

# auth.fastapi
make_current_user_dependency(
    secret_provider: Callable[[], str],       # zero-arg callable, NOT a string
    algorithms: Sequence[str] = ("HS256",),
    require_exp: bool = False,
) -> Callable[..., int]
```

The secret is a **callable** so each service keeps resolving it from
its own `Settings` (works with tests that patch/reload settings).
Typical one-liner in the service:

```python
# app/auth.py becomes:
from auth.fastapi import make_current_user_dependency
from app.config import settings

get_current_user_id = make_current_user_dependency(lambda: settings.JWT_SECRET)
```

Routers keep importing `from app.auth import get_current_user_id` —
zero router changes.

## 4. Delete after adoption

- The JWT-decode + dependency portion of `app/auth.py` (in most
  services this is the whole file, replaced by the 3-line shim above).
- Local tests of the decode/401 flow (the package has 28 tests); keep
  tests asserting the service's own route protection.

Do NOT move into the shared package:

- `create_access_token` — only user-service mints tokens.
  budget-service's `make_service_auth_header` is backlog **P3-02**
  (known antipattern); leave it in place, do not port it.
- `hash_password` / `verify_password` — belong to user-service only.

## 5. Divergence warnings (found by sampling, 2026-07-14)

1. **account-service `app/auth.py` is 241 lines because it is a stale
   monolith copy** (header still says `# backend/auth.py`). It carries
   `create_access_token`, `hash_password`/`verify_password` (bcrypt +
   passlib import), `TokenData`/`Token` Pydantic models,
   `verify_token_and_get_user_id`, an import-time `SECRET_KEY`
   assertion, and a ~35-line commented-out account-resolution
   dependency. A grep found **no usages** of the minting/hashing/helper
   symbols anywhere else in account-service — dead code. Its
   `get_current_user_id` matches the shared three-message flow exactly.
   Adoption: replace the whole file with the shim; also drop `bcrypt`
   and `passlib` from account-service deps if nothing else uses them.
   The import-time SECRET_KEY validation, if worth keeping, belongs in
   `app/config.py`.

2. **gateway-service `app/auth.py` (101 lines) is NOT a copy — mostly
   preserve it.** Its `get_user_id_from_headers` uses different 401
   details ("Authentication required" / "Invalid token"), omits
   `WWW-Authenticate`, and treats a non-Bearer header the same as a
   missing one (2 messages, not 3). Swapping in the shared dependency
   is a wire-visible behavior change for gateway clients — decide
   explicitly, don't drive-by change it. Its
   `get_account_id_from_headers` (httpx ownership verification against
   account-service) is gateway-specific and must be **preserved**; at
   most swap its inner `_decode_token` for `auth.jwt.decode_token`
   (note: raises instead of returning `None`).

3. **goal-service (and similar OAuth2PasswordBearer variants)**: uses
   `fastapi.security.OAuth2PasswordBearer`, one generic 401 detail
   ("Invalid or expired token") for all failure modes, and FastAPI's
   built-in "Not authenticated" for a missing header. Adopting the
   shared dependency changes 401 `detail` strings and drops the OpenAPI
   oauth2 security scheme from the docs. Functionally equivalent;
   update any tests asserting exact 401 bodies.

4. **`decode_token` contract change everywhere**: local copies return
   `None` on failure; the shared one raises `InvalidTokenError`. Any
   non-dependency caller (e.g. account-service's
   `verify_token_and_get_user_id`, websocket/manual header parsing)
   needs a try/except.

`require_exp` defaults to `False`, matching every service today (tokens
without `exp` are accepted; expired `exp` is still rejected). Turning
on `require_exp=True` is an explicit opt-in per service — never flip it
as part of adoption.

## 6. Verification checklist

- [ ] `uv lock && uv sync` succeeds; only the new package in the diff
- [ ] Service test suite green (`uv run pytest`) — including 401-detail
      assertions updated where flagged above
- [ ] `uv run ruff check .` clean
- [ ] `docker compose build <svc>` succeeds (repo-root context)
- [ ] Live smoke: request without token → 401
      `Missing authentication token`; garbage token → 401
      `Invalid or expired authentication token`; valid token issued by
      user-service (`sub` claim) → 200 with correct user scoping
- [ ] Cross-service: a token minted by user-service works against the
      migrated service (the `sub` vs `user_id` normalization is the
      whole point)
