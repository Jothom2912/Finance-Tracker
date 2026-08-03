"""Unit tests for the CategorizationService pipeline orchestrator."""

from __future__ import annotations

import pytest
from app.application.categorization_service import CategorizationService
from app.application.dto import CategorizeRequestDTO
from app.domain.value_objects import CategorizationResult, CategorizationTier, Confidence


class FakeRuleEngine:
    """Fake that matches 'netto' -> subcategory 1, category 1."""

    def match(self, description: str, amount: float) -> CategorizationResult | None:
        if "netto" in description.lower():
            return CategorizationResult(
                category_id=1,
                subcategory_id=1,
                tier=CategorizationTier.RULE,
                confidence=Confidence.HIGH,
            )
        return None


class FailingRuleEngine:
    """Fake that always raises."""

    def match(self, description: str, amount: float) -> CategorizationResult | None:
        raise RuntimeError("Rule engine exploded")


class FakeMlCategorizer:
    """Tier 2 fake: matches 'irma' -> subcategory 2, category 2."""

    def predict(self, description: str) -> CategorizationResult | None:
        if "irma" in description.lower():
            return CategorizationResult(
                category_id=2,
                subcategory_id=2,
                tier=CategorizationTier.ML,
                confidence=Confidence.MEDIUM,
            )
        return None


class FailingMlCategorizer:
    def predict(self, description: str) -> CategorizationResult | None:
        raise RuntimeError("ML exploded")


class FakeLlmCategorizer:
    """Tier 3 fake: matches 'føtex' -> subcategory 3, category 3."""

    def predict(self, description: str, amount: float) -> CategorizationResult | None:
        if "føtex" in description.lower():
            return CategorizationResult(
                category_id=3,
                subcategory_id=3,
                tier=CategorizationTier.LLM,
                confidence=Confidence.LOW,
            )
        return None


@pytest.fixture()
def service() -> CategorizationService:
    return CategorizationService(
        rule_engine=FakeRuleEngine(),
        fallback_subcategory_id=99,
        fallback_category_id=8,
    )


@pytest.fixture()
def failing_service() -> CategorizationService:
    return CategorizationService(
        rule_engine=FailingRuleEngine(),
        fallback_subcategory_id=99,
        fallback_category_id=8,
    )


class TestCategorizationPipeline:
    async def test_rule_engine_hit(self, service: CategorizationService) -> None:
        request = CategorizeRequestDTO(description="Netto Nordhavn", amount=-150.0)
        response = await service.categorize(request)
        assert response.category_id == 1
        assert response.subcategory_id == 1
        assert response.tier == "rule"
        assert response.confidence == "high"
        assert response.needs_review is False

    async def test_fallback_when_no_match(self, service: CategorizationService) -> None:
        request = CategorizeRequestDTO(description="Unknown merchant", amount=-50.0)
        response = await service.categorize(request)
        assert response.category_id == 8
        assert response.subcategory_id == 99
        assert response.tier == "fallback"
        assert response.confidence == "low"
        assert response.needs_review is True

    async def test_fallback_log_excludes_hostile_description(
        self, service: CategorizationService, caplog: pytest.LogCaptureFixture
    ) -> None:
        hostile = "private-bank-text-that-must-never-be-logged"
        await service.categorize(CategorizeRequestDTO(description=hostile, amount=-10.0))
        assert hostile not in caplog.text

    async def test_tier_failure_falls_through(self, failing_service: CategorizationService) -> None:
        request = CategorizeRequestDTO(description="Anything", amount=-50.0)
        response = await failing_service.categorize(request)
        assert response.tier == "fallback"
        assert response.confidence == "low"

    async def test_batch_categorization(self, service: CategorizationService) -> None:
        requests = [
            CategorizeRequestDTO(description="Netto City", amount=-100.0),
            CategorizeRequestDTO(description="Unknown shop", amount=-50.0),
        ]
        responses = await service.categorize_batch(requests)
        assert len(responses) == 2
        assert responses[0].tier == "rule"
        assert responses[1].tier == "fallback"


class TestOptionalTiers:
    """The ML and LLM branches had no coverage before P2-31.

    They were touched to bind the tier to a local before closing over it (mypy
    does not narrow `self._ml` inside a lambda). These pin the tier-ordering
    shapes so that change is demonstrably behaviour-neutral rather than
    asserted to be — they pass against the pre-change code too.
    """

    @staticmethod
    def _service(*, ml: object = None, llm: object = None) -> CategorizationService:
        return CategorizationService(
            rule_engine=FakeRuleEngine(),
            fallback_subcategory_id=99,
            fallback_category_id=8,
            ml_categorizer=ml,  # type: ignore[arg-type]  # structural fakes
            llm_categorizer=llm,  # type: ignore[arg-type]
        )

    async def test_rules_win_over_ml(self) -> None:
        svc = self._service(ml=FakeMlCategorizer())
        response = await svc.categorize(CategorizeRequestDTO(description="Netto Irma", amount=-10.0))
        assert response.tier == "rule"

    async def test_ml_runs_when_rules_miss(self) -> None:
        svc = self._service(ml=FakeMlCategorizer())
        response = await svc.categorize(CategorizeRequestDTO(description="Irma Torvehallerne", amount=-10.0))
        assert response.tier == "ml"
        assert response.category_id == 2

    async def test_llm_runs_when_ml_misses(self) -> None:
        svc = self._service(ml=FakeMlCategorizer(), llm=FakeLlmCategorizer())
        response = await svc.categorize(CategorizeRequestDTO(description="Føtex Amager", amount=-10.0))
        assert response.tier == "llm"
        assert response.category_id == 3

    async def test_ml_raising_falls_through_to_llm(self) -> None:
        svc = self._service(ml=FailingMlCategorizer(), llm=FakeLlmCategorizer())
        response = await svc.categorize(CategorizeRequestDTO(description="Føtex Amager", amount=-10.0))
        assert response.tier == "llm"

    async def test_all_tiers_miss_reaches_fallback(self) -> None:
        svc = self._service(ml=FakeMlCategorizer(), llm=FakeLlmCategorizer())
        response = await svc.categorize(CategorizeRequestDTO(description="Ukendt butik", amount=-10.0))
        assert response.tier == "fallback"
        assert response.needs_review is True
