"""REST-lag-tests for ``POST /api/v1/transactions/import-csv`` — P2-29's guards.

Until now this endpoint had **no** coverage on its HTTP boundary at all.
``tests/unit/test_transaction_service.py::TestImportCSV`` calls
``service.import_csv(...)`` directly with ``bytes`` and a mocked UoW, which by
construction cannot see any of what is tested here: the multipart binding,
``UploadFile.size``, ``content_type``, or the middleware that runs before
routing.  So these are the endpoint's first adapter tests, not new cases on
existing ones.

**The two layers are genuinely two layers, and that is what this file pins.**
Both the middleware (``app/main.py``) and the handler guard
(``rest_api.py::_reject_unimportable_upload``) answer 413 on an oversized
upload, and for a normal request the middleware always wins — a multipart body
is never smaller than the file part it carries, so any file over the limit
implies a ``Content-Length`` over the limit.  That would make the handler guard
look like dead code.  It is not:
``test_handler_guard_catches_a_chunked_upload_the_middleware_cannot`` sends the
same payload with **no** ``Content-Length`` (chunked), the middleware passes it
through, and the handler guard is what returns 413.  The two assertions
distinguish the layers by their ``detail`` strings on purpose; if someone
deletes either guard, exactly one of the two tests goes red.

Requires Docker running: the guard runs *inside* the handler body, so FastAPI
has already resolved ``get_transaction_service`` (and therefore a DB session)
even for a request that is about to be rejected.  Real Postgres for the same
reason as ``test_transaction_list_api.py``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from alembic import command
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_URL = "/api/v1/transactions/import-csv"

# Handed out one-per-test by the ``user_id`` fixture; see its docstring.
_next_user = 5150

_HEADER = "date,amount,transaction_type,account_id,account_name,description\n"


def _csv(rows: int) -> bytes:
    """A valid internal-format CSV with ``rows`` importable rows."""
    body = "".join(f"2026-03-{(i % 28) + 1:02d},{100 + i}.00,expense,7,Checking,row {i}\n" for i in range(rows))
    return (_HEADER + body).encode("utf-8")


@pytest.fixture(scope="module")
def postgres() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16") as pg:
        yield pg


@pytest.fixture(scope="module")
def _migrated_db(postgres: PostgresContainer) -> None:
    url = postgres.get_connection_url()
    os.environ["DATABASE_URL"] = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    os.environ.setdefault("JWT_SECRET", "test-secret")

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")


def _auth(user_id: int) -> dict[str, str]:
    """Mint a token the service will accept — see test_transaction_list_api.py."""
    from app.config import settings
    from jose import jwt

    token = jwt.encode(
        {"user_id": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user_id() -> int:
    """A fresh user per test.

    ``import_csv`` commits, and the dedup key is
    ``(user_id, account_id, date, amount, description)`` — so two tests posting
    the same generated CSV under one user would make the second one report
    ``duplicates_skipped`` instead of ``imported``.  Scoping by user is cheaper
    than truncating between tests and keeps each test's assertion about its own
    rows.
    """
    global _next_user
    _next_user += 1
    return _next_user


@pytest.fixture()
async def client(postgres: PostgresContainer, _migrated_db: None) -> AsyncIterator[httpx.AsyncClient]:
    """An ASGI client whose DB session is created in *this* test's event loop.

    ``app.database.engine`` is built at import time and pools asyncpg
    connections, which are bound to the loop that opened them.  pytest-asyncio
    gives each test function its own loop, so reusing the module-level engine
    fails the second test with "another operation is in progress".  Overriding
    ``get_db`` with a per-test engine is the same fix
    ``test_transaction_list_api.py`` uses.
    """
    from app.database import get_db
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    url = postgres.get_connection_url()
    async_url = url.replace("postgresql://", "postgresql+asyncpg://").replace("psycopg2", "asyncpg")
    engine = create_async_engine(async_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        app.dependency_overrides[get_db] = lambda: session
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http
        app.dependency_overrides.clear()

    await engine.dispose()


# ── The guards must not change a valid import (non-goal 1) ──────────


async def test_a_valid_csv_still_imports_with_the_guards_in_place(client: httpx.AsyncClient, user_id: int) -> None:
    response = await client.post(
        _URL,
        headers=_auth(user_id),
        files={"file": ("bank.csv", _csv(3), "text/csv")},
        data={"bank_format": "internal"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imported"] == 3
    assert body["skipped"] == 0
    assert body["errors"] == []


@pytest.mark.parametrize(
    "content_type",
    [
        "text/csv",
        "application/csv",
        "text/plain",
        # Windows sends this for .csv when Excel is the registered handler, and
        # browsers fall back to octet-stream.  Both are real, so both must pass
        # — a stricter allowlist would reject genuine Danish bank exports.
        "application/vnd.ms-excel",
        "application/octet-stream",
        "text/csv; charset=utf-8",
    ],
)
async def test_the_allowlist_accepts_what_real_clients_actually_send(
    client: httpx.AsyncClient, user_id: int, content_type: str
) -> None:
    response = await client.post(
        _URL,
        headers=_auth(user_id),
        files={"file": ("bank.csv", _csv(1), content_type)},
        data={"bank_format": "internal"},
    )

    assert response.status_code == 200, f"{content_type} was rejected: {response.text}"


# ── MIME: a typo filter, not a security boundary ────────────────────


async def test_a_pdf_is_rejected_as_unsupported_media_type(client: httpx.AsyncClient, user_id: int) -> None:
    response = await client.post(
        _URL,
        headers=_auth(user_id),
        files={"file": ("statement.pdf", b"%PDF-1.7\n%%EOF\n", "application/pdf")},
        data={"bank_format": "internal"},
    )

    assert response.status_code == 415
    assert "application/pdf" in response.json()["detail"]


# ── Size: the middleware layer ──────────────────────────────────────


async def test_middleware_rejects_a_declared_oversize_before_routing(
    client: httpx.AsyncClient, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """413 from the middleware, identified by its own detail string.

    The limit is monkeypatched rather than sending 10 MiB: both guards read
    ``settings`` at call time, so a small limit exercises the same branch for
    the price of a few hundred bytes.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "CSV_MAX_BYTES", 200)

    response = await client.post(
        _URL,
        headers=_auth(user_id),
        files={"file": ("bank.csv", _csv(40), "text/csv")},
        data={"bank_format": "internal"},
    )

    assert response.status_code == 413
    # "Forespørgslen" = the middleware; the handler says "CSV-filen".
    assert "Forespørgslen er for stor" in response.json()["detail"]


# ── Size: the handler layer, which the middleware cannot cover ──────


async def test_handler_guard_catches_a_chunked_upload_the_middleware_cannot(
    client: httpx.AsyncClient, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """413 from the handler on a request with no ``Content-Length``.

    This is the test that proves the handler guard is not shadowed by the
    middleware.  Passing an iterator as ``content`` makes httpx use chunked
    transfer encoding and omit ``Content-Length``, so the middleware has
    nothing to check — but starlette still counts the received bytes, so
    ``UploadFile.size`` is populated and the handler guard fires.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "CSV_MAX_BYTES", 200)

    boundary = "----p229boundary"
    payload = _csv(40)
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="bank.csv"\r\n'
            "Content-Type: text/csv\r\n\r\n"
        ).encode()
        + payload
        + (
            f"\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="bank_format"\r\n\r\n'
            f"internal\r\n"
            f"--{boundary}--\r\n"
        ).encode()
    )

    async def chunks() -> AsyncIterator[bytes]:
        yield body

    response = await client.post(
        _URL,
        headers={**_auth(user_id), "Content-Type": f"multipart/form-data; boundary={boundary}"},
        content=chunks(),
    )

    assert "content-length" not in {k.lower() for k in response.request.headers}, (
        "httpx sent a Content-Length, so this exercised the middleware, not the handler guard"
    )
    assert response.status_code == 413
    assert "CSV-filen er for stor" in response.json()["detail"]


# ── Rows: the cap that actually binds for well-formed files ─────────


async def test_too_many_rows_is_a_400_that_names_the_limit(
    client: httpx.AsyncClient, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row cap is reported through the existing CSVImportException → 400.

    Deliberately not 413: this reaches the user in the same channel as every
    other CSV complaint, and the message carries the number she needs.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "CSV_MAX_ROWS", 3)

    response = await client.post(
        _URL,
        headers=_auth(user_id),
        files={"file": ("bank.csv", _csv(10), "text/csv")},
        data={"bank_format": "internal"},
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "for mange rækker" in detail
    assert "3" in detail


async def test_a_file_exactly_at_the_row_cap_is_accepted(
    client: httpx.AsyncClient, user_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The boundary belongs to the accepted side — an off-by-one here would
    reject the largest legitimate import rather than the first illegitimate one."""
    from app.config import settings

    monkeypatch.setattr(settings, "CSV_MAX_ROWS", 5)

    response = await client.post(
        _URL,
        headers=_auth(user_id),
        files={"file": ("bank.csv", _csv(5), "text/csv")},
        data={"bank_format": "internal"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["imported"] == 5
