"""F1-02 — rules routes are registered, JWT-scoped and map domain
exceptions to the documented HTTP statuses. DB-free: service + auth
dependencies are overridden with stubs (same pattern as the category
router test)."""

from __future__ import annotations

from app.application.dto import RuleResponseDTO
from app.auth import get_current_user_id
from app.dependencies import get_rule_service
from app.domain.exceptions import DuplicateRule, RuleNotFound, SubCategoryNotFound
from app.main import app
from fastapi.testclient import TestClient

_RULE = RuleResponseDTO(
    id=1,
    pattern_type="keyword",
    pattern_value="netto",
    subcategory_id=3,
    subcategory_name="Dagligvarer",
    category_id=1,
    category_name="Mad & drikke",
    priority=50,
    active=True,
)


class _StubRuleService:
    def __init__(self) -> None:
        self.seen_user_ids: list[int] = []

    async def list_rules(self, user_id: int) -> list[RuleResponseDTO]:
        self.seen_user_ids.append(user_id)
        return [_RULE]

    async def create_rule(self, user_id: int, dto) -> RuleResponseDTO:  # type: ignore[no-untyped-def]
        self.seen_user_ids.append(user_id)
        if dto.pattern_value == "netto":
            raise DuplicateRule(dto.pattern_value)
        if dto.subcategory_id == 999:
            raise SubCategoryNotFound(dto.subcategory_id)
        return _RULE.model_copy(update={"pattern_value": dto.pattern_value, "priority": dto.priority})

    async def update_rule(self, user_id: int, rule_id: int, dto) -> RuleResponseDTO:  # type: ignore[no-untyped-def]
        self.seen_user_ids.append(user_id)
        if rule_id == 404:
            raise RuleNotFound(rule_id)
        return _RULE.model_copy(update={"active": dto.active if dto.active is not None else True})

    async def delete_rule(self, user_id: int, rule_id: int) -> None:
        self.seen_user_ids.append(user_id)
        if rule_id == 404:
            raise RuleNotFound(rule_id)


def _client(stub: _StubRuleService, user_id: int = 7) -> TestClient:
    app.dependency_overrides[get_rule_service] = lambda: stub
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    return TestClient(app)


def _cleanup() -> None:
    app.dependency_overrides.clear()


class TestRulesRoutes:
    def test_list_returns_rules_for_the_jwt_user(self) -> None:
        stub = _StubRuleService()
        try:
            resp = _client(stub, user_id=42).get("/api/v1/rules/")
            assert resp.status_code == 200
            assert resp.json()[0]["pattern_value"] == "netto"
            assert resp.json()[0]["is_learned"] is False
            assert stub.seen_user_ids == [42]
        finally:
            _cleanup()

    def test_create_returns_201(self) -> None:
        try:
            resp = _client(_StubRuleService()).post(
                "/api/v1/rules/",
                json={"pattern_value": "rema", "subcategory_id": 3},
            )
            assert resp.status_code == 201
            assert resp.json()["pattern_value"] == "rema"
            assert resp.json()["priority"] == 50
        finally:
            _cleanup()

    def test_create_duplicate_maps_to_409(self) -> None:
        try:
            resp = _client(_StubRuleService()).post(
                "/api/v1/rules/",
                json={"pattern_value": "netto", "subcategory_id": 3},
            )
            assert resp.status_code == 409
        finally:
            _cleanup()

    def test_create_unknown_subcategory_maps_to_404(self) -> None:
        try:
            resp = _client(_StubRuleService()).post(
                "/api/v1/rules/",
                json={"pattern_value": "rema", "subcategory_id": 999},
            )
            assert resp.status_code == 404
        finally:
            _cleanup()

    def test_create_priority_out_of_bounds_is_422(self) -> None:
        """[20, 90]: users may not outrank learned rules (10) or sink
        below seeds (100)."""
        try:
            client = _client(_StubRuleService())
            for priority in (10, 100):
                resp = client.post(
                    "/api/v1/rules/",
                    json={"pattern_value": "rema", "subcategory_id": 3, "priority": priority},
                )
                assert resp.status_code == 422
        finally:
            _cleanup()

    def test_update_unknown_rule_maps_to_404(self) -> None:
        try:
            resp = _client(_StubRuleService()).put("/api/v1/rules/404", json={"active": False})
            assert resp.status_code == 404
        finally:
            _cleanup()

    def test_delete_returns_204(self) -> None:
        try:
            resp = _client(_StubRuleService()).delete("/api/v1/rules/1")
            assert resp.status_code == 204
        finally:
            _cleanup()

    def test_routes_require_auth(self) -> None:
        """Without a JWT the shared auth dependency must reject."""
        app.dependency_overrides[get_rule_service] = lambda: _StubRuleService()
        try:
            resp = TestClient(app).get("/api/v1/rules/")
            assert resp.status_code in (401, 403)
        finally:
            _cleanup()
