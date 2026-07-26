"""REST-lag-tests for ``GET /api/v1/transactions/`` — the service's most-read endpoint.

Until now this endpoint had **no** coverage on its HTTP boundary: the filter
semantics were tested at the repository level
(``test_transaction_repository_filters.py``) and the service level
(``tests/unit/test_transaction_service.py``), but nothing exercised the
adapter — the query-parameter binding, the auth dependency, the response
shape.  It landed **first**, pinning the bare-array contract, so that step 11's
breaking change showed up as a handful of named assertion flips rather than as
the endpoint's first test and its shape change in one commit.  Since
``92ab86f0``+ the body is the envelope ``{"total_count", "items"}`` and
``_rows`` below is the single place that knows it.

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


def _rows(response: httpx.Response) -> list[dict]:
    """The page's rows out of the envelope.

    One place in this file knows where rows live, so a future shape change is
    one edit here plus the named shape tests below — not a sweep over every
    filter assertion.
    """
    return response.json()["items"]


def _total(response: httpx.Response) -> int:
    return response.json()["total_count"]


# --------------------------------------------------------------------------
# Response shape — the envelope P1-14 step 11 introduced (breaking).
# --------------------------------------------------------------------------


async def test_list_returns_an_envelope_with_a_total_and_items(client: httpx.AsyncClient) -> None:
    """The contract after step 11: ``{"total_count": int, "items": [...]}``.

    Written as its own test so the breaking change reads as a named contract
    change in the diff rather than as fallout in an unrelated filter test.  It
    replaces ``test_list_returns_a_bare_json_array``, which asserted
    ``isinstance(body, list)`` — that is the assertion this endpoint's whole
    problem lived behind: an array has nowhere to put a total.
    """
    response = await _get(client, _FEB_EXPENSES)

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert set(body) == {"total_count", "items"}
    assert isinstance(body["total_count"], int)
    assert all(isinstance(row, dict) and "id" in row for row in body["items"])


async def test_rows_carry_the_denormalised_category_name(client: httpx.AsyncClient) -> None:
    response = await _get(client, {"account_id": 1, "category_id": 1})

    assert response.status_code == 200
    assert [(r["description"], r["category_name"]) for r in _rows(response)] == [("in range #1", "Mad & drikke")]


async def test_the_total_sees_the_category_filter_too(client: httpx.AsyncClient) -> None:
    """A separate test, asserting *only* the total.

    ``category_id`` is the one filter no other assertion counts under, so
    without this test dropping its branch from ``_filter_clauses`` fails the row
    assertions only — and mutation check 1 would be blind to half of the shared
    clause it is supposed to prove.  Kept apart from the row assertion above so
    it cannot be masked by that one failing first.
    """
    response = await _get(client, {"account_id": 1, "category_id": 1})

    assert _total(response) == 1


# --------------------------------------------------------------------------
# Scoping and filters — the query params actually reach the SQL.
# --------------------------------------------------------------------------


async def test_only_the_callers_own_rows_are_returned(client: httpx.AsyncClient) -> None:
    """``user_id`` comes from the token, never from a query param.

    The seeded ``other user`` row sits inside the requested account and date
    range, so it would be returned by any filter set that forgot the scope.
    """
    response = await _get(client, {"account_id": 1, "start_date": "2026-02-01", "end_date": "2026-02-28"})

    descriptions = [r["description"] for r in _rows(response)]
    assert "other user" not in descriptions
    assert all(r["user_id"] == _USER for r in _rows(response))
    # The total is scoped too — a count that forgot the user would report 5.
    assert _total(response) == 4


async def test_all_filters_combine_in_one_request(client: httpx.AsyncClient) -> None:
    response = await _get(client, _FEB_EXPENSES)

    # Excludes: dates outside the range, the income row on 2026-02-10, the
    # other account and the other user.  Newest first.
    assert [r["description"] for r in _rows(response)] == ["in range #3", "in range #2", "in range #1"]
    # The count must apply the *same* predicates: this is the assertion that
    # fails if a filter is dropped from ``_filter_clauses`` and only the row
    # path keeps it (or vice versa).
    assert _total(response) == 3


async def test_newest_first_with_id_as_tiebreak(client: httpx.AsyncClient) -> None:
    response = await _get(client, {"account_id": 1, "start_date": "2026-02-10", "end_date": "2026-02-10"})

    # Same date — the later-created (higher id) row comes first, which is what
    # makes OFFSET paging stable across requests.
    assert [r["description"] for r in _rows(response)] == ["income same date", "in range #2"]


async def test_unknown_transaction_type_is_rejected(client: httpx.AsyncClient) -> None:
    response = await _get(client, {"transaction_type": "refund"})

    assert response.status_code == 422


# --------------------------------------------------------------------------
# Pagination — the mechanism P1-14 needs, and the ceiling it exposes.
# --------------------------------------------------------------------------


async def test_the_default_page_is_still_50_but_no_longer_silent(client: httpx.AsyncClient) -> None:
    """The defect P1-14 fixes, pinned at the HTTP boundary.

    The ceiling itself is unchanged: 55 rows match, 50 come back.  What changed
    is that the response now *says so* — ``total_count`` is 55 beside 50 items,
    so a caller can tell this from "that is all there was".  That
    indistinguishability is how the same ceiling bit twice, here and in
    analytics' backfill.
    """
    response = await _get(client, _FILLER_ONLY)

    assert response.status_code == 200
    assert len(_rows(response)) == 50
    assert _total(response) == _FILLER_ROWS


async def test_skip_reaches_the_rest_of_the_set(client: httpx.AsyncClient) -> None:
    """The two pages partition the filtered set, and both report the same total.

    Asserted as a set property rather than by description order, because what
    matters is that no row is lost between pages and none is served twice.  The
    total is the same on both pages — it describes the set, not the window, so
    ``skip`` must not reach the ``COUNT``.
    """
    first = await _get(client, {**_FILLER_ONLY, "limit": 50})
    second = await _get(client, {**_FILLER_ONLY, "skip": 50, "limit": 50})

    page_one = {r["id"] for r in _rows(first)}
    page_two = {r["id"] for r in _rows(second)}

    assert len(page_one) == 50
    assert len(page_two) == _FILLER_ROWS - 50
    assert page_one.isdisjoint(page_two)
    assert len(page_one | page_two) == _FILLER_ROWS
    assert _total(first) == _total(second) == _FILLER_ROWS


async def test_limit_truncates_a_filtered_set(client: httpx.AsyncClient) -> None:
    """A page smaller than its filter set — three rows match, two are returned.

    ``total_count`` reads 3, not 2.  This is the case that makes
    ``total_count = len(items)`` a *failing* implementation rather than a
    passing one, and the reason this file seeds more than one page.
    """
    response = await _get(client, {**_FEB_EXPENSES, "limit": 2})

    assert [r["description"] for r in _rows(response)] == ["in range #3", "in range #2"]
    assert _total(response) == 3


async def test_skip_past_the_end_returns_an_empty_page_with_a_nonzero_total(
    client: httpx.AsyncClient,
) -> None:
    """An empty page is not an empty period, and the envelope can say so.

    This is what the frontend's clamp reads: ``items == []`` with
    ``total_count == 3`` means "you are past the end", where ``total_count == 0``
    would mean "there is nothing here".  Collapsing the two is how an empty
    state gets to lie.
    """
    response = await _get(client, {**_FEB_EXPENSES, "skip": 99})

    assert response.status_code == 200
    assert _rows(response) == []
    assert _total(response) == 3


@pytest.mark.parametrize(
    ("params", "offending_field"),
    [
        ({"limit": 201}, "limit"),
        ({"limit": 0}, "limit"),
        ({"skip": -1}, "skip"),
    ],
)
async def test_out_of_range_pagination_is_a_422_not_a_500(
    client: httpx.AsyncClient, params: dict, offending_field: str
) -> None:
    """Out-of-range paging is a client error, and it names the field.

    All three of these returned **500** before the ``Query(...)`` bounds
    landed: a bare annotation is type-validated but unbounded, so the value
    travelled as far as ``TransactionFiltersDTO`` inside the handler body,
    where a ``pydantic.ValidationError`` is no longer something FastAPI can
    translate into a response.  A caller could not tell "you asked for too
    much" from "the service is broken".
    """
    response = await _get(client, params)

    assert response.status_code == 422
    assert offending_field in str(response.json())


async def test_the_boundary_values_are_still_accepted(client: httpx.AsyncClient) -> None:
    """``limit=200`` must stay legal: analytics' backfill pages at exactly 200.

    ``analytics-service/app/tools/backfill.py:48`` sets ``PAGE_SIZE = 200``,
    which sits *on* the ``le`` bound with no margin — an off-by-one here would
    422 every page of a backfill run rather than degrade.  ``skip=0`` is the
    common case and must not be treated as "unset".
    """
    for params in ({"limit": 200}, {"limit": 1}, {"skip": 0}):
        response = await _get(client, {**_FILLER_ONLY, **params})
        assert response.status_code == 200, params


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
