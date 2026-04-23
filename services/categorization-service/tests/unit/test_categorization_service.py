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
