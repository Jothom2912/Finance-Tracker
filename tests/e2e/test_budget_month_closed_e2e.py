"""End-to-end test for the budget.month_closed event path.

Proves the full chain: close_month → outbox → RabbitMQ → goal-service consumer → allocation.
Tests both happy path and two idempotency layers:
  - closed_at guard (publisher-side: repeated close_month → 409)
  - source_key dedup (consumer-side: redelivered event → no double allocation)

Prerequisites:
    docker compose up -d --build --wait

    # Goal-service needs manual migration (Dockerfile doesn't auto-run):
    docker compose exec goal-service alembic upgrade head

Run:
    pytest tests/e2e/test_budget_month_closed_e2e.py -v -s
"""

from __future__ import annotations

import asyncio
import base64
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
GOAL_SERVICE = "http://localhost:8006/api/v1"
TRANSACTION_SERVICE = "http://localhost:8002/api/v1"
BUDGET_SERVICE = "http://localhost:8003/api/v1"
CATEGORIZATION_SERVICE = "http://localhost:8005/api/v1"
ANALYTICS_SERVICE = "http://localhost:8012/api/v1/analytics"
RABBITMQ_API = "http://localhost:15672/api"

POLL_TIMEOUT = 15.0
# Forbruget skal hele vejen gennem outbox → RabbitMQ → ES-projektionen, og
# projektions-consumeren kører med prefetch 1 (P2-19), så én ack-rundtur pr.
# event. Rundere end de 15s ovenfor med vilje — det er en længere kæde.
SPEND_POLL_TIMEOUT = 40.0

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


async def _poll_until(
    check_fn,
    timeout: float = POLL_TIMEOUT,
    interval: float = 1.0,
    desc: str = "condition",
):
    deadline = asyncio.get_event_loop().time() + timeout
    last_result = None
    while asyncio.get_event_loop().time() < deadline:
        last_result = await check_fn()
        if last_result:
            return last_result
        await asyncio.sleep(interval)
    pytest.fail(f"Timed out waiting for {desc} (last result: {last_result})")


async def _await_spend_on_read_side(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    account_id: int,
    expected: float,
) -> float:
    """Bloker indtil analytics rapporterer ``expected`` som junis samlede forbrug.

    Siden P1-13 læser ``close_month`` forbruget fra analytics' ``/overview``
    (``budget-service/app/adapters/outbound/analytics_port.py``), altså fra
    ES-read-modellen — ikke fra transaction-service synkront. Skriv-svaret på
    de tre POST'er nedenfor siger derfor intet om hvad lukningen kommer til at
    se: uden denne gate læser den ``spent=0``, allokerer hele budgettet, og
    alle tre tests fejler med ``5000.0 == 2000.0`` (P2-30).

    Vi poller det tal lukningen selv slår op — samme endpoint, samme
    datointerval som ``budget_period(2026, 6, 1)`` — frem for at sove en
    tilfældig periode. Testen venter allerede på *allokeringen*; det der
    manglede var at vente på *forbruget*.
    """
    deadline = asyncio.get_event_loop().time() + SPEND_POLL_TIMEOUT
    observed: float | None = None
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(
            f"{ANALYTICS_SERVICE}/overview?account_id={account_id}&start_date=2026-06-01&end_date=2026-06-30",
            headers=headers,
        )
        if resp.status_code == 200:
            observed = float(resp.json().get("total_expenses", 0.0))
            if abs(observed - expected) < 0.01:
                return observed
        await asyncio.sleep(1.0)

    pytest.fail(
        f"Forbruget nåede aldrig ES-read-modellen: analytics rapporterer "
        f"total_expenses={observed} for konto {account_id} i juni 2026, "
        f"forventede {expected}. close_month ville have læst det tal og "
        f"allokeret et for stort overskud."
    )


def _psql_budget(sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres-budget",
            "psql",
            "-U",
            "budget_service",
            "-d",
            "budget_service",
            "-t",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _psql_goals(sql: str) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres-goals",
            "psql",
            "-U",
            "goal_service",
            "-d",
            "goals",
            "-t",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def test_context():
    """Seed all required test data: user, account, goal, category, transactions, budget."""
    uid = uuid.uuid4().hex[:8]
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        # 1. Register user
        resp = await client.post(
            f"{USER_SERVICE}/register",
            json={
                "username": f"e2e_budget_{uid}",
                "email": f"e2e_budget_{uid}@example.com",
                "password": "SecurePass123!",
            },
        )
        assert resp.status_code == 201, f"Registration failed: {resp.text}"
        user_id = resp.json()["id"]
        token = _make_token(user_id)
        headers = _auth(token)

        # 2. Wait for default account (created by saga)
        async def _check_account():
            r = await client.get(ACCOUNT_SERVICE, headers=headers)
            if r.status_code == 200:
                accs = r.json()
                defaults = [a for a in accs if a.get("name") == "Default Account"]
                if defaults:
                    return defaults[0]
            return None

        account = await _poll_until(_check_account, desc="default account creation")
        account_id = account["idAccount"]

        # 3. Create goal
        resp = await client.post(
            f"{GOAL_SERVICE}/goals",
            headers=headers,
            json={
                "name": "E2E Savings Goal",
                "target_amount": 100000.0,
                "current_amount": 0.0,
                "target_date": "2027-12-31",
                "Account_idAccount": account_id,
            },
        )
        assert resp.status_code == 201, f"Goal creation failed: {resp.text}"
        goal_id = resp.json()["idGoal"]

        # 4. Set is_default_savings_goal=true via SQL (not exposed in API)
        _psql_goals(f'UPDATE goals SET is_default_savings_goal = TRUE WHERE "idGoal" = {goal_id};')

        # 5. Use a seeded expense category (exists in both categorization-service
        #    and transaction-service via category sync events)
        resp = await client.get(
            f"{CATEGORIZATION_SERVICE}/categories",
            headers=headers,
        )
        assert resp.status_code == 200, f"Category list failed: {resp.text}"
        expense_cats = [c for c in resp.json() if c["type"] == "expense"]
        assert expense_cats, "No expense categories found in categorization-service"
        category_id = expense_cats[0]["id"]
        category_name = expense_cats[0]["name"]

        # 6. Create transactions (total 3000 in expenses)
        for i, amount in enumerate([1000.0, 1200.0, 800.0]):
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
                    "description": f"E2E expense {i}",
                    "date": "2026-06-10",
                },
            )
            assert resp.status_code == 201, f"Transaction creation failed: {resp.text}"

        # 6b. Vent på at de tre udgifter er nået ES-read-modellen, som er der
        #     close_month henter forbruget fra (P1-13). Uden denne gate lukker
        #     test 1 måneden mod spent=0.
        await _await_spend_on_read_side(client, headers, account_id, expected=3000.0)

        # 7. Create monthly budget (total 5000)
        resp = await client.post(
            f"{BUDGET_SERVICE}/monthly-budgets?account_id={account_id}",
            headers=headers,
            json={
                "month": 6,
                "year": 2026,
                "lines": [{"category_id": category_id, "amount": 5000.0}],
            },
        )
        assert resp.status_code == 201, f"Budget creation failed: {resp.text}"
        budget_id = resp.json()["id"]

    return {
        "user_id": user_id,
        "account_id": account_id,
        "goal_id": goal_id,
        "budget_id": budget_id,
        "category_id": category_id,
        "token": token,
        "expected_surplus": 2000.0,
    }


class TestBudgetMonthClosedE2E:
    """Tests run in order — happy path first, then idempotency."""

    @pytest.mark.asyncio(loop_scope="module")
    async def test_1_happy_path_close_month_allocates_surplus(self, test_context):
        """close_month → event → goal allocation = expected surplus."""
        ctx = test_context
        headers = _auth(ctx["token"])

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            # Close the month (budgeted=5000, spent=3000 → surplus=2000)
            resp = await client.post(
                f"{BUDGET_SERVICE}/monthly-budgets/close"
                f"?account_id={ctx['account_id']}&month=6&year=2026&budget_start_day=1",
                headers=headers,
            )
            assert resp.status_code == 204, f"close_month failed: {resp.text}"

            # Wait for event to propagate (outbox poll 2s + consumer processing)
            async def _check_goal_allocation():
                r = await client.get(
                    f"{GOAL_SERVICE}/goals/{ctx['goal_id']}",
                    headers=headers,
                )
                if r.status_code == 200:
                    current = r.json().get("current_amount", 0)
                    if current > 0:
                        return current
                return None

            allocated = await _poll_until(
                _check_goal_allocation,
                desc="goal surplus allocation",
            )
            assert allocated == ctx["expected_surplus"], f"Expected surplus {ctx['expected_surplus']}, got {allocated}"

        # Verify outbox row is published (filter by aggregate_id to avoid stale rows)
        outbox_status = _psql_budget(
            "SELECT status FROM outbox_events "
            f"WHERE event_type = 'budget.month_closed' AND aggregate_id = '{ctx['budget_id']}';"
        )
        assert "published" in outbox_status, f"Outbox row not published: {outbox_status}"

        # Verify closed_at is set
        closed_at = _psql_budget(f"SELECT closed_at FROM monthly_budgets WHERE id = {ctx['budget_id']};")
        assert closed_at and closed_at != "", f"closed_at not set on budget {ctx['budget_id']}"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_2a_closed_at_guard_rejects_duplicate_close(self, test_context):
        """Second close_month → 409, no new event, allocation unchanged."""
        ctx = test_context
        headers = _auth(ctx["token"])

        count_before = int(
            _psql_budget(
                "SELECT COUNT(*) FROM outbox_events "
                f"WHERE event_type = 'budget.month_closed' AND aggregate_id = '{ctx['budget_id']}';"
            )
        )

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.post(
                f"{BUDGET_SERVICE}/monthly-budgets/close"
                f"?account_id={ctx['account_id']}&month=6&year=2026&budget_start_day=1",
                headers=headers,
            )
            assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

            # Verify goal allocation unchanged
            resp = await client.get(
                f"{GOAL_SERVICE}/goals/{ctx['goal_id']}",
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["current_amount"] == ctx["expected_surplus"], (
                "Goal amount should not have changed after rejected close"
            )

        # Verify no new outbox row was created
        count_after = int(
            _psql_budget(
                "SELECT COUNT(*) FROM outbox_events "
                f"WHERE event_type = 'budget.month_closed' AND aggregate_id = '{ctx['budget_id']}';"
            )
        )
        assert count_after == count_before, f"Outbox rows increased from {count_before} to {count_after} despite 409"

    @pytest.mark.asyncio(loop_scope="module")
    async def test_2b_consumer_dedup_handles_redelivery(self, test_context):
        """Manually republish same event → consumer deduplicates, no double allocation."""
        ctx = test_context
        headers = _auth(ctx["token"])

        # Read the published outbox event payload from budget-DB
        event_json = _psql_budget(
            "SELECT payload_json FROM outbox_events "
            f"WHERE event_type = 'budget.month_closed' AND aggregate_id = '{ctx['budget_id']}';"
        )
        assert event_json, "No outbox event found to republish"

        # Publish the same event directly to RabbitMQ via management API
        rabbitmq_auth = base64.b64encode(b"guest:guest").decode()
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.post(
                f"{RABBITMQ_API}/exchanges/%2F/finans_tracker.events/publish",
                headers={"Authorization": f"Basic {rabbitmq_auth}"},
                json={
                    "properties": {
                        "delivery_mode": 2,
                        "content_type": "application/json",
                    },
                    "routing_key": "budget.month_closed",
                    "payload": event_json,
                    "payload_encoding": "string",
                },
            )
            assert resp.status_code == 200, f"RabbitMQ publish failed: {resp.text}"

        # Wait for consumer to process the redelivered event
        await asyncio.sleep(5)

        # Verify goal allocation is STILL the same (not doubled)
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                f"{GOAL_SERVICE}/goals/{ctx['goal_id']}",
                headers=headers,
            )
            assert resp.status_code == 200
            current = resp.json()["current_amount"]
            assert current == ctx["expected_surplus"], (
                f"Goal amount changed to {current} after redelivery — "
                f"expected {ctx['expected_surplus']} (dedup failed!)"
            )

        # Verify exactly one allocation row exists
        allocation_count = int(
            _psql_goals(
                "SELECT COUNT(*) FROM goal_allocation_history "
                f"WHERE source_key = 'budget.month_closed:{ctx['account_id']}:2026:6';"
            )
        )
        assert allocation_count == 1, (
            f"Expected exactly 1 allocation row, found {allocation_count} — "
            "source_key dedup did not prevent double allocation"
        )
