"""TAX-14 — direction crosses the HTTP boundary, through a real engine.

The service's own suite calls the pipeline object directly and the client's
suite mocks the transport, so nothing exercised the field that actually decides
which half of the rule set applies. These tests drive the real router with a
real ``ConstrainedRuleEngine`` — no stub service — so a direction that is
dropped, renamed or defaulted anywhere in the request path fails here.

DB-free: ``build_categorization_service`` is monkeypatched to return a service
built on an in-memory rule set, and TestClient is not used as a context manager
so startup warmup never hits the DB.
"""

from __future__ import annotations

import pytest
from app.adapters.inbound import categorize_api
from app.adapters.outbound.rule_engine import ConstrainedRuleEngine, PersistedSeedRule
from app.application.categorization_service import CategorizationService
from app.domain.value_objects import Confidence
from app.main import app
from fastapi.testclient import TestClient

KEY = "internal-key-for-tests"

FALLBACK_SUBCATEGORY = 139
FALLBACK_CATEGORY = 29
OUTGOING_SUBCATEGORY = 174
OUTGOING_CATEGORY = 36

# One outgoing description rule is enough: the question is whether direction
# survives the trip, not how rich the rule set is.
RULES = [
    PersistedSeedRule(
        target_subcategory_id=OUTGOING_SUBCATEGORY,
        target_category_id=OUTGOING_CATEGORY,
        match_field="description",
        operator="contains",
        direction="outgoing",
        confidence=Confidence.MEDIUM,
        pattern="mobilepay",
    )
]


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def _build(user_id: int | None = None) -> CategorizationService:
        return CategorizationService(
            rule_engine=ConstrainedRuleEngine(RULES),
            fallback_subcategory_id=FALLBACK_SUBCATEGORY,
            fallback_category_id=FALLBACK_CATEGORY,
        )

    monkeypatch.setattr(categorize_api, "build_categorization_service", _build)
    monkeypatch.setattr(categorize_api.settings, "INTERNAL_API_KEY", KEY)
    monkeypatch.setattr(categorize_api.rule_engine_provider, "semantic_key_for", lambda _id: None)
    return TestClient(app)


def _post(client: TestClient, **body: object) -> dict:
    response = client.post("/api/v1/categorize/", json=body, headers={"X-Internal-Api-Key": KEY})
    assert response.status_code == 200, response.text
    return response.json()


class TestDirectionDecidesTheOutcome:
    def test_outgoing_reaches_the_rule(self, client: TestClient) -> None:
        # Unsigned amount, exactly as transaction-service stores it.
        body = _post(client, description="MobilePay Telenor 24836308437046", amount=299.0, direction="outgoing")
        assert body["tier"] == "rule"
        assert (body["category_id"], body["subcategory_id"]) == (OUTGOING_CATEGORY, OUTGOING_SUBCATEGORY)

    def test_incoming_does_not(self, client: TestClient) -> None:
        body = _post(client, description="MobilePay Telenor 24836308437046", amount=299.0, direction="incoming")
        assert body["tier"] == "fallback"
        assert body["subcategory_id"] == FALLBACK_SUBCATEGORY

    def test_the_sign_of_the_amount_no_longer_decides_anything(self, client: TestClient) -> None:
        # The regression this plan removes: a negative amount used to be the
        # only way to reach an outgoing rule.
        positive = _post(client, description="MobilePay Telenor", amount=299.0, direction="outgoing")
        negative = _post(client, description="MobilePay Telenor", amount=-299.0, direction="outgoing")
        assert positive["subcategory_id"] == negative["subcategory_id"] == OUTGOING_SUBCATEGORY


class TestContractIsEnforcedAtTheBoundary:
    def test_a_missing_direction_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/",
            json={"description": "MobilePay Telenor", "amount": 299.0},
            headers={"X-Internal-Api-Key": KEY},
        )
        # 422 rather than a plausible wrong answer: an omitted direction is a
        # caller bug, and defaulting it is what broke categorization before.
        assert response.status_code == 422

    def test_an_invalid_direction_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/",
            json={"description": "MobilePay Telenor", "amount": 299.0, "direction": "sideways"},
            headers={"X-Internal-Api-Key": KEY},
        )
        assert response.status_code == 422

    def test_batch_requires_it_on_every_item(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/categorize/batch",
            json=[
                {"description": "MobilePay A", "amount": 10.0, "direction": "outgoing"},
                {"description": "MobilePay B", "amount": 20.0},
            ],
            headers={"X-Internal-Api-Key": KEY},
        )
        assert response.status_code == 422
