"""End-to-end test for the mid-month budget-alert path (F2-03).

Proves the full chain: budget-alert-scheduler run_once → evaluate_alerts →
outbox → RabbitMQ → notification-consumer → in-app notification, plus:
  - 80% and 100% are distinct notifications (threshold in the source_key)
  - stateless re-emit + notification-service source_key dedup = notified once
  - owner-scoping (a second user sees nothing)

The scheduler container sleeps 6h, so the tick is driven deterministically by
calling ``run_once`` in the budget-service container with an explicit ``today``.

Prerequisites:
    docker compose up -d --build --wait budget-service budget-outbox-worker \
        notification-service notification-consumer

Run:
    pytest tests/e2e/test_budget_threshold_alert_e2e.py -v -s
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio
from jose import jwt

from ._env import JWT_ALGORITHM, jwt_secret

USER_SERVICE = "http://localhost:8001/api/v1/users"
ACCOUNT_SERVICE = "http://localhost:8004/api/v1/accounts/"
TRANSACTION_SERVICE = "http://localhost:8002/api/v1"
BUDGET_SERVICE = "http://localhost:8003/api/v1"
CATEGORIZATION_SERVICE = "http://localhost:8005/api/v1"
NOTIFICATION_SERVICE = "http://localhost:8008/api/v1"
ANALYTICS_SERVICE = "http://localhost:8012/api/v1"

POLL_TIMEOUT = 20.0

# Running-period sweep: budget + transactions + tick all use 07/2026.
YEAR, MONTH = 2026, 7
TICK_TODAY = "date(2026, 7, 18)"  # → July has 31 days ⇒ days_remaining = 13
EXPECTED_DAYS_REMAINING = 13

# Every seed description embeds this keyword so the *rule* tier decides the
# category. Without it the descriptions match nothing, all tiers are exhausted,
# and the fallback tier rewrites the rows to "Diverse" — asynchronously, which
# is what made this suite flaky. Keep the keyword and the category in sync;
# both come from the global (user_id IS NULL) taxonomy seeded by cat-service.
RULE_KEYWORD = "REMA1000"
RULE_CATEGORY_NAME = "Mad & drikke"

pytestmark = pytest.mark.e2e


def _make_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=JWT_ALGORITHM)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _poll_until(check_fn, timeout: float = POLL_TIMEOUT, interval: float = 1.0, desc: str = "condition"):
    deadline = asyncio.get_event_loop().time() + timeout
    last_result = None
    while asyncio.get_event_loop().time() < deadline:
        last_result = await check_fn()
        if last_result:
            return last_result
        await asyncio.sleep(interval)
    pytest.fail(f"Timed out waiting for {desc} (last result: {last_result})")


def _psql_notifications(sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres-notifications",
            "psql",
            "-U",
            "notification_service",
            "-d",
            "notifications",
            "-t",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _psql_transactions(sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres-transactions",
            "psql",
            "-U",
            "transaction_service",
            "-d",
            "transactions",
            "-t",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _effective_expense_category(account_id: int) -> tuple[int, float] | None:
    """The category the account's July expenses actually landed in after async
    categorization (which may move them off the id supplied at create time),
    with the summed amount. None until at least one expense row exists."""
    out = _psql_transactions(
        "SELECT category_id, SUM(amount) FROM transactions "
        f"WHERE account_id = {account_id} AND transaction_type = 'expense' "
        f"AND date >= '{YEAR}-{MONTH:02d}-01' AND date <= '{YEAR}-{MONTH:02d}-28' "
        "GROUP BY category_id ORDER BY SUM(amount) DESC LIMIT 1;"
    )
    if not out:
        return None
    cat_str, sum_str = out.split("|")
    return int(cat_str.strip()), float(sum_str.strip())


async def _await_category(account_id: int, expected_cat_id: int, expected_sum: float, desc: str) -> int:
    """Wait until the account's July expenses have landed in the category the
    rule engine is *known* to assign, at the expected sum.

    This used to wait for the dominant category to be "stable" — two identical
    reads 2s apart — and budget against whatever it saw. That is a guess, not a
    barrier: async categorization always rewrites these rows, so the fixture
    raced the correction. When the correction was slow the fixture budgeted
    against the create-time category, spend later landed elsewhere, and the
    per-line alert never fired. See dev-notes finding
    2026-07-27-e2e-alert-categorization-race.

    Now the expected category is derived from a global keyword rule
    (``RULE_KEYWORD`` → ``RULE_CATEGORY_NAME``), so there is a right answer to
    wait for and a wrong answer to fail on.
    """

    async def _settled():
        got = _effective_expense_category(account_id)
        if not got:
            return None
        cat_id, total = got
        if cat_id != expected_cat_id or abs(total - expected_sum) >= 0.01:
            return None
        return got

    cat_id, _ = await _poll_until(_settled, timeout=40.0, interval=2.0, desc=desc)
    return cat_id


async def _await_analytics_spend(token: str, account_id: int, category_id: int, expected: float, desc: str) -> None:
    """Wait until *analytics* reports the spend — not just the transaction DB.

    The scheduler does not read transactions; it reads ``expenses_by_category``
    off analytics' overview endpoint (P1-13, see
    ``decisions/2026-07-25-budget-spend-from-analytics.md``). Analytics is an
    Elasticsearch read-side fed by its own projection consumer, so it lags the
    transaction DB by an unbounded amount.

    Waiting on postgres-transactions and then ticking is therefore the wrong
    barrier: the tick reports ``failed_upstream: 0`` and emits nothing, because
    from analytics' point of view the money has not been spent yet. Poll the
    same source the scheduler reads.
    """

    async def _visible():
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(
                f"{ANALYTICS_SERVICE}/analytics/overview",
                params={
                    "account_id": account_id,
                    "start_date": f"{YEAR}-{MONTH:02d}-01",
                    "end_date": f"{YEAR}-{MONTH:02d}-31",
                },
                headers=_auth(token),
            )
            if r.status_code != 200:
                return None
        for bucket in r.json().get("expenses_by_category") or []:
            if bucket.get("category_id") == category_id and abs(float(bucket.get("amount", 0.0)) - expected) < 0.01:
                return bucket
        return None

    await _poll_until(_visible, timeout=60.0, interval=2.0, desc=desc)


def _run_alert_tick() -> str:
    """Drive one scheduler sweep against the live stack (real DB + HTTP + outbox)."""
    script = (
        "import asyncio; from datetime import date; "
        "from app.database import async_session_factory; "
        "from app.workers.budget_alert_scheduler import run_once; "
        f"print(asyncio.run(run_once(async_session_factory, {TICK_TODAY}, [80, 100])))"
    )
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "budget-service", "python", "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


async def _create_expense(client, headers, account_id, category_id, category_name, amount, desc):
    resp = await client.post(
        f"{TRANSACTION_SERVICE}/transactions",
        headers=headers,
        json={
            "account_id": account_id,
            "account_name": "Default Account",
            "category_id": category_id,
            "category_name": category_name,
            "amount": amount,
            "transaction_type": "expense",
            "description": desc,
            "date": f"{YEAR}-{MONTH:02d}-10",
        },
    )
    assert resp.status_code == 201, f"Transaction creation failed: {resp.text}"


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def test_context():
    """Seed: user, default account, expense category, transactions (850), budget line (1000)."""
    uid = uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.post(
            f"{USER_SERVICE}/register",
            json={
                "username": f"e2e_alert_{uid}",
                "email": f"e2e_alert_{uid}@example.com",
                "password": "SecurePass123!",
            },
        )
        assert resp.status_code == 201, f"Registration failed: {resp.text}"
        user_id = resp.json()["id"]
        headers = _auth(_make_token(user_id))

        async def _check_account():
            r = await client.get(ACCOUNT_SERVICE, headers=headers)
            if r.status_code == 200:
                defaults = [a for a in r.json() if a.get("name") == "Default Account"]
                if defaults:
                    return defaults[0]
            return None

        account = await _poll_until(_check_account, desc="default account creation")
        account_id = account["idAccount"]

        resp = await client.get(f"{CATEGORIZATION_SERVICE}/categories", headers=headers)
        assert resp.status_code == 200, f"Category list failed: {resp.text}"
        expense_cats = [c for c in resp.json() if c["type"] == "expense"]
        assert expense_cats, "No expense categories found"
        # Budget against the category the rule tier will assign, not against
        # whichever category happens to sort first — the latter is a leftover
        # from earlier runs and guarantees a drift the fixture then races.
        seed_cat = next((c for c in expense_cats if c["name"] == RULE_CATEGORY_NAME), None)
        assert seed_cat is not None, (
            f"expected global category {RULE_CATEGORY_NAME!r} for keyword {RULE_KEYWORD!r}; "
            f"found {[c['name'] for c in expense_cats]}"
        )

        # 850 of 1000 budget ⇒ 85% (crosses 80, not 100)
        for i, amount in enumerate([500.0, 350.0]):
            await _create_expense(
                client, headers, account_id, seed_cat["id"], seed_cat["name"], amount, f"{RULE_KEYWORD} E2E {i}"
            )

        # Create-time category and rule-tier outcome now agree, so this is a
        # barrier with a right answer rather than a stability guess.
        category_id = await _await_category(
            account_id, seed_cat["id"], expected_sum=850.0, desc="categorization to settle at 850"
        )
        category_name = seed_cat["name"]

        resp = await client.post(
            f"{BUDGET_SERVICE}/monthly-budgets?account_id={account_id}",
            headers=headers,
            json={"month": MONTH, "year": YEAR, "lines": [{"category_id": category_id, "amount": 1000.0}]},
        )
        assert resp.status_code == 201, f"Budget creation failed: {resp.text}"

        # The scheduler reads spend from analytics, so the ES projection must
        # have caught up before any tick can see the 850.
        await _await_analytics_spend(
            _make_token(user_id), account_id, category_id, 850.0, desc="analytics to report 850"
        )

    return {
        "user_id": user_id,
        "account_id": account_id,
        "category_id": category_id,
        "category_name": category_name,
        "token": _make_token(user_id),
    }


def _source_key(account_id: int, category_id: int, threshold: int) -> str:
    return f"budget.line_threshold_crossed:{account_id}:{YEAR}:{MONTH}:{category_id}:{threshold}"


class TestBudgetThresholdAlertE2E:
    @pytest.mark.asyncio(loop_scope="module")
    async def test_1_crossing_80_creates_notification(self, test_context):
        ctx = test_context
        # The sweep is global (all open budgets of the period), and the shared dev
        # DB may hold leftover budgets from prior runs — so we assert on THIS
        # account's source_keys, never the global tick counter.
        out = _run_alert_tick()
        assert "'failed_upstream': 0" in out, f"tick had upstream failures: {out}"

        key80 = _source_key(ctx["account_id"], ctx["category_id"], 80)

        async def _check_row():
            rows = _psql_notifications(f"SELECT type, body FROM notifications WHERE source_key = '{key80}';")
            return rows if rows else None

        row = await _poll_until(_check_row, desc="80% notification row")
        assert "budget_threshold_crossed" in row
        assert f"85% af {ctx['category_name']} brugt, {EXPECTED_DAYS_REMAINING} dage tilbage." in row

        # And it shows in the owner's feed API
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(f"{NOTIFICATION_SERVICE}/notifications", headers=_auth(ctx["token"]))
            assert r.status_code == 200
            titles = [n["title"] for n in r.json()]
            assert "Budget-advarsel" in titles, f"feed missing warning: {titles}"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_2_crossing_100_is_a_distinct_notification(self, test_context):
        ctx = test_context
        headers = _auth(ctx["token"])
        # Push spend over budget: +400 ⇒ 1250 total = 125%
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            await _create_expense(
                client,
                headers,
                ctx["account_id"],
                ctx["category_id"],
                ctx["category_name"],
                400.0,
                f"{RULE_KEYWORD} E2E over",
            )

        await _await_category(
            ctx["account_id"],
            ctx["category_id"],
            expected_sum=1250.0,
            desc="over-budget spend to settle at 1250",
        )
        await _await_analytics_spend(
            ctx["token"], ctx["account_id"], ctx["category_id"], 1250.0, desc="analytics to report 1250"
        )

        _run_alert_tick()  # both 80 and 100 now at/over threshold for this account

        key100 = _source_key(ctx["account_id"], ctx["category_id"], 100)

        async def _check_row():
            rows = _psql_notifications(f"SELECT type, body FROM notifications WHERE source_key = '{key100}';")
            return rows if rows else None

        row = await _poll_until(_check_row, desc="100% notification row")
        assert "125% af" in row

        # Exactly two notification rows for this account/period now (80 + 100)
        count = int(
            _psql_notifications(
                "SELECT COUNT(*) FROM notifications WHERE source_key LIKE "
                f"'budget.line_threshold_crossed:{ctx['account_id']}:{YEAR}:{MONTH}:%';"
            )
        )
        assert count == 2, f"expected 2 threshold notifications, found {count}"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_3_re_tick_does_not_duplicate(self, test_context):
        ctx = test_context
        # Stateless scheduler re-emits both crossings; downstream source_key dedups.
        _run_alert_tick()
        await asyncio.sleep(5)  # let the consumer ACK the duplicates

        count = int(
            _psql_notifications(
                "SELECT COUNT(*) FROM notifications WHERE source_key LIKE "
                f"'budget.line_threshold_crossed:{ctx['account_id']}:{YEAR}:{MONTH}:%';"
            )
        )
        assert count == 2, f"dedup failed: expected 2 rows, found {count}"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_4_owner_scoping_second_user_sees_nothing(self, test_context):
        # A fresh user's feed must not contain the first user's budget alerts.
        other = _make_token(999_000_001)
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(f"{NOTIFICATION_SERVICE}/notifications", headers=_auth(other))
            assert r.status_code == 200
            assert r.json() == [], f"foreign feed not empty: {r.json()}"
