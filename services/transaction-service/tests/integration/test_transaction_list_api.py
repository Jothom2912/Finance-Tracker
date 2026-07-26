"""REST-lag-tests for ``GET /api/v1/transactions/`` — the service's most-read endpoint.

Until now this endpoint had **no** coverage on its HTTP boundary: the filter
semantics were tested at the repository level
(``test_transaction_repository_filters.py``) and the service level
(``tests/unit/test_transaction_service.py``), but nothing exercised the
adapter — the query-parameter binding, the auth dependency, the response
shape.  P1-14 is about to change that response shape, so this file lands
**first** and pins the *current* contract.  Step 11 then flips a handful of
named assertions instead of writing the endpoint's first test and its
breaking change in one commit.

Two deliberate deviations from ``notification-service``'s ASGI-test template:

*   **Real Postgres, not ``sqlite+aiosqlite``.**  The assertions here are
    about ``LIMIT``/``OFFSET`` applied *after* ``ORDER BY date DESC, id DESC``
    — and once ``count_filtered`` arrives, about a ``COUNT`` that has to agree
    with those rows.  That is precisely the area where SQLite is permitted to
    differ from Postgres, so testing it on SQLite would prove the wrong thing.
*   **Seeding goes through the repository, not ``POST /transactions/``.**
    ``get_transaction_service`` injects a real ``CategorizationClient``, so a
    POST per row would fire an outbound HTTP call with a live timeout.

The seeded rows are never committed: the app and the seeding share one
session, and closing it rolls back, so every test starts from a clean slate
without dropping and re-migrating the schema.

Requires Docker running.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_USER = 4141
_OTHER_USER = 4242

# Enough filler rows on their own account to exceed the endpoint's default
# ``limit=50`` — the ceiling P1-14 is about.  Without a filtered set that is
# larger than the requested page, "total_count = len(items)" would be a
# correct implementation and step 11's mutation check 3 could not fail.
_FILLER_ACCOUNT = 9
_FILLER_ROWS = 55

# (account_id, type, date, description, user_id, category_id) — creation order
# matters: ids ascend, so the two rows sharing 2026-02-10 test the id
# tie-break that makes pagination deterministic.
_ROWS = [
    (1, "expense", date(2026, 1, 15), "before range", _USER, None),
    (1, "expense", date(2026, 2, 1), "in range #1", _USER, 1),
    (1, "expense", date(2026, 2, 10), "in range #2", _USER, None),
    (1, "income", date(2026, 2, 10), "income same date", _USER, None),
    (1, "expense", date(2026, 2, 20), "in range #3", _USER, None),
    (1, "expense", date(2026, 3, 5), "after range", _USER, None),
    (2, "expense", date(2026, 2, 15), "other account", _USER, None),
    (1, "expense", date(2026, 2, 12), "other user", _OTHER_USER, None),
]

_FILLER_ONLY = {"account_id": _FILLER_ACCOUNT}
_FEB_EXPENSES = {
    "account_id": 1,
    "start_date": "2026-02-01",
    "end_date": "2026-02-28",
    "transaction_type": "expense",
}


@pytest.fixture(scope="module")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def _migrated_db(postgres):
    url = postgres.get_connection_url()
    os.environ["DATABASE_URL"] = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ.setdefault("JWT_SECRET", "test-secret")

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")


def _token(user_id: int) -> str:
    """Mint a token the service will accept.

    The secret is read off the live ``settings`` object rather than a literal,
    so this keeps working regardless of which test module in this directory
    imported ``app.config`` first.  No ``exp`` claim is needed:
    ``require_exp`` defaults to ``False`` in the shared auth package (P2-02),
    and ``decode_token`` accepts either ``user_id`` or ``sub``.
    """
    from app.config import settings
    from jose import jwt

    return jwt.encode({"user_id": user_id}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _auth(user_id: int = _USER) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id)}"}


@pytest.fixture()
async def client(postgres, _migrated_db) -> AsyncIterator[httpx.AsyncClient]:
    from app.adapters.outbound.postgres_transaction_repository import PostgresTransactionRepository
    from app.database import get_db
    from app.domain.entities import TransactionType
    from app.main import app

    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        repository = PostgresTransactionRepository(session)
        for account_id, tx_type, tx_date, description, user_id, category_id in _ROWS:
            await repository.create(
                user_id=user_id,
                account_id=account_id,
                account_name="Checking",
                # category_id=1 is seeded as "Mad & drikke" by migration 005.
                category_id=category_id,
                category_name="Mad & drikke" if category_id is not None else None,
                amount=Decimal("100.00"),
                transaction_type=TransactionType(tx_type),
                description=description,
                tx_date=tx_date,
            )
        for i in range(_FILLER_ROWS):
            await repository.create(
                user_id=_USER,
                account_id=_FILLER_ACCOUNT,
                account_name="Filler",
                category_id=None,
                category_name=None,
                amount=Decimal("10.00"),
                transaction_type=TransactionType.EXPENSE,
                description=f"filler {i:02d}",
                # Dates repeat across the month on purpose: the id tie-break is
                # what makes paging over them deterministic, not the date.
                tx_date=date(2026, 5, 1) + timedelta(days=i % 28),
            )

        # The app must see the *same* uncommitted session, or it opens its own
        # transaction and finds an empty table.
        app.dependency_overrides[get_db] = lambda: session
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http
        app.dependency_overrides.clear()

    await engine.dispose()


async def _get(client: httpx.AsyncClient, params: dict) -> httpx.Response:
    return await client.get("/api/v1/transactions/", params=params, headers=_auth())


# --------------------------------------------------------------------------
# Response shape — this is what P1-14 step 11 deliberately breaks.
# --------------------------------------------------------------------------


async def test_list_returns_a_bare_json_array(client: httpx.AsyncClient) -> None:
    """The current contract: the body IS the array, with nowhere to put a total.

    This assertion is the one step 11 flips to ``{"total_count", "items"}``.
    It is written as its own test so the breaking change shows up as a named
    contract change in the diff rather than as fallout in an unrelated test.
    """
    response = await _get(client, _FEB_EXPENSES)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert all(isinstance(row, dict) and "id" in row for row in body)


async def test_rows_carry_the_denormalised_category_name(client: httpx.AsyncClient) -> None:
    response = await _get(client, {"account_id": 1, "category_id": 1})

    assert response.status_code == 200
    assert [(r["description"], r["category_name"]) for r in response.json()] == [("in range #1", "Mad & drikke")]


# --------------------------------------------------------------------------
# Scoping and filters — the query params actually reach the SQL.
# --------------------------------------------------------------------------


async def test_only_the_callers_own_rows_are_returned(client: httpx.AsyncClient) -> None:
    """``user_id`` comes from the token, never from a query param.

    The seeded ``other user`` row sits inside the requested account and date
    range, so it would be returned by any filter set that forgot the scope.
    """
    response = await _get(client, {"account_id": 1, "start_date": "2026-02-01", "end_date": "2026-02-28"})

    descriptions = [r["description"] for r in response.json()]
    assert "other user" not in descriptions
    assert all(r["user_id"] == _USER for r in response.json())


async def test_all_filters_combine_in_one_request(client: httpx.AsyncClient) -> None:
    response = await _get(client, _FEB_EXPENSES)

    # Excludes: dates outside the range, the income row on 2026-02-10, the
    # other account and the other user.  Newest first.
    assert [r["description"] for r in response.json()] == ["in range #3", "in range #2", "in range #1"]


async def test_newest_first_with_id_as_tiebreak(client: httpx.AsyncClient) -> None:
    response = await _get(client, {"account_id": 1, "start_date": "2026-02-10", "end_date": "2026-02-10"})

    # Same date — the later-created (higher id) row comes first, which is what
    # makes OFFSET paging stable across requests.
    assert [r["description"] for r in response.json()] == ["income same date", "in range #2"]


async def test_unknown_transaction_type_is_rejected(client: httpx.AsyncClient) -> None:
    response = await _get(client, {"transaction_type": "refund"})

    assert response.status_code == 422


# --------------------------------------------------------------------------
# Pagination — the mechanism P1-14 needs, and the ceiling it exposes.
# --------------------------------------------------------------------------


async def test_default_limit_silently_caps_the_page_at_50(client: httpx.AsyncClient) -> None:
    """The defect P1-14 fixes, pinned at the HTTP boundary.

    55 rows match; 50 come back; and — the actual problem — the response says
    nothing at all about the five that did not.  A caller cannot distinguish
    this from "that is all there was", which is exactly how the same ceiling
    bit twice, here and in analytics' backfill.
    """
    response = await _get(client, _FILLER_ONLY)

    assert response.status_code == 200
    assert len(response.json()) == 50


async def test_skip_reaches_the_rest_of_the_set(client: httpx.AsyncClient) -> None:
    """Paging already works — only the total is missing.

    Asserted as a set property rather than by description order, because what
    matters is that the two pages partition the filtered set exactly: no row
    lost between pages, none served twice.
    """
    first = await _get(client, {**_FILLER_ONLY, "limit": 50})
    second = await _get(client, {**_FILLER_ONLY, "skip": 50, "limit": 50})

    page_one = {r["id"] for r in first.json()}
    page_two = {r["id"] for r in second.json()}

    assert len(page_one) == 50
    assert len(page_two) == _FILLER_ROWS - 50
    assert page_one.isdisjoint(page_two)
    assert len(page_one | page_two) == _FILLER_ROWS


async def test_limit_truncates_a_filtered_set(client: httpx.AsyncClient) -> None:
    """A page smaller than its filter set — three rows match, two are returned.

    Step 11's ``total_count`` must read 3 here.  This is the case that makes
    ``total_count = len(items)`` a *failing* implementation rather than a
    passing one.
    """
    response = await _get(client, {**_FEB_EXPENSES, "limit": 2})

    assert [r["description"] for r in response.json()] == ["in range #3", "in range #2"]


async def test_skip_past_the_end_returns_an_empty_page(client: httpx.AsyncClient) -> None:
    response = await _get(client, {**_FEB_EXPENSES, "skip": 99})

    assert response.status_code == 200
    assert response.json() == []


# --------------------------------------------------------------------------
# Auth — the endpoint is not reachable without a valid token.
# --------------------------------------------------------------------------


async def test_missing_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/transactions/")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_malformed_authorization_header_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/transactions/", headers={"Authorization": "Token abc"})

    assert response.status_code == 401


async def test_token_signed_with_the_wrong_secret_is_401(client: httpx.AsyncClient) -> None:
    from jose import jwt

    forged = jwt.encode({"user_id": _USER}, "not-the-shared-secret", algorithm="HS256")

    response = await client.get("/api/v1/transactions/", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
