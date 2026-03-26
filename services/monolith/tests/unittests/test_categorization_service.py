"""
Unit tests for CategorizationService (pipeline orchestrator).

Tests all tier combinations: rule-only, rule+ML, rule+ML+LLM,
tier failures, batch processing, and fallback behavior.
"""

import pytest

from backend.category.application.categorization_service import (
    CategorizationOutput,
    CategorizationService,
    TransactionInput,
)
from backend.category.domain.value_objects import (
    CategorizationResult,
    CategorizationTier,
    Confidence,
)

FALLBACK_CAT_ID = 99
FALLBACK_SUBCAT_ID = 88

RULE_RESULT = CategorizationResult(
    category_id=1, subcategory_id=10, tier=CategorizationTier.RULE, confidence=Confidence.HIGH,
)
ML_RESULT = CategorizationResult(
    category_id=2, subcategory_id=20, tier=CategorizationTier.ML, confidence=Confidence.MEDIUM,
)
LLM_RESULT = CategorizationResult(
    category_id=3, subcategory_id=30, tier=CategorizationTier.LLM, confidence=Confidence.LOW,
)


# ──────────────────────────────────────────────
# Fake tier implementations (satisfy Protocol structurally)
# ──────────────────────────────────────────────


class FakeRuleEngine:
    def __init__(self, result: CategorizationResult | None = None):
        self._result = result
        self.call_count = 0

    def match(self, description: str, amount: float) -> CategorizationResult | None:
        self.call_count += 1
        return self._result


class FakeMlCategorizer:
    def __init__(self, result: CategorizationResult | None = None):
        self._result = result
        self.call_count = 0

    def predict(self, description: str) -> CategorizationResult | None:
        self.call_count += 1
        return self._result


class FakeLlmCategorizer:
    def __init__(
        self,
        result: CategorizationResult | None = None,
        batch_results: list[CategorizationResult] | None = None,
    ):
        self._result = result
        self._batch_results = batch_results
        self.call_count = 0
        self.batch_call_count = 0

    def predict(self, description: str, amount: float) -> CategorizationResult:
        self.call_count += 1
        return self._result or CategorizationResult(
            category_id=FALLBACK_CAT_ID,
            subcategory_id=FALLBACK_SUBCAT_ID,
            tier=CategorizationTier.LLM,
            confidence=Confidence.LOW,
        )

    def predict_batch(
        self, transactions: list[tuple[str, float]]
    ) -> list[CategorizationResult]:
        self.batch_call_count += 1
        if self._batch_results is not None:
            return self._batch_results
        return [self.predict(d, a) for d, a in transactions]


class FailingRuleEngine:
    def match(self, description: str, amount: float) -> CategorizationResult | None:
        raise RuntimeError("Rule engine crashed")


class FailingMlCategorizer:
    def predict(self, description: str) -> CategorizationResult | None:
        raise RuntimeError("ML model crashed")


class FailingLlmCategorizer:
    def predict(self, description: str, amount: float) -> CategorizationResult:
        raise RuntimeError("LLM crashed")

    def predict_batch(
        self, transactions: list[tuple[str, float]]
    ) -> list[CategorizationResult]:
        raise RuntimeError("LLM batch crashed")


# ──────────────────────────────────────────────
# Single transaction categorization
# ──────────────────────────────────────────────


class TestCategorizeSingle:
    def _make_service(
        self,
        rule_engine: object = None,
        ml: object = None,
        llm: object = None,
    ) -> CategorizationService:
        return CategorizationService(
            rule_engine=rule_engine or FakeRuleEngine(None),
            fallback_subcategory_id=FALLBACK_SUBCAT_ID,
            fallback_category_id=FALLBACK_CAT_ID,
            ml_categorizer=ml,
            llm_categorizer=llm,
        )

    def _txn(self, desc: str = "Netto 2150", amount: float = -150.0) -> TransactionInput:
        return TransactionInput(description=desc, amount=amount, reference_id=42)

    def test_rule_match_stops_pipeline(self) -> None:
        rules = FakeRuleEngine(RULE_RESULT)
        ml = FakeMlCategorizer(ML_RESULT)
        svc = self._make_service(rule_engine=rules, ml=ml)

        output = svc.categorize(self._txn())

        assert output.result == RULE_RESULT
        assert output.reference_id == 42
        assert output.needs_review is False
        assert rules.call_count == 1
        assert ml.call_count == 0

    def test_ml_fallback_when_rules_miss(self) -> None:
        rules = FakeRuleEngine(None)
        ml = FakeMlCategorizer(ML_RESULT)
        svc = self._make_service(rule_engine=rules, ml=ml)

        output = svc.categorize(self._txn())

        assert output.result == ML_RESULT
        assert output.result.tier == CategorizationTier.ML
        assert rules.call_count == 1
        assert ml.call_count == 1

    def test_llm_fallback_when_rules_and_ml_miss(self) -> None:
        rules = FakeRuleEngine(None)
        ml = FakeMlCategorizer(None)
        llm = FakeLlmCategorizer(LLM_RESULT)
        svc = self._make_service(rule_engine=rules, ml=ml, llm=llm)

        output = svc.categorize(self._txn())

        assert output.result == LLM_RESULT
        assert output.needs_review is True
        assert llm.call_count == 1

    def test_absolute_fallback_when_all_tiers_miss(self) -> None:
        svc = self._make_service(rule_engine=FakeRuleEngine(None))

        output = svc.categorize(self._txn())

        assert output.result.category_id == FALLBACK_CAT_ID
        assert output.result.subcategory_id == FALLBACK_SUBCAT_ID
        assert output.result.tier == CategorizationTier.FALLBACK
        assert output.result.confidence == Confidence.LOW
        assert output.needs_review is True

    def test_rule_engine_crash_falls_through_to_fallback(self) -> None:
        svc = self._make_service(rule_engine=FailingRuleEngine())

        output = svc.categorize(self._txn())

        assert output.result.tier == CategorizationTier.FALLBACK

    def test_ml_crash_falls_through_to_llm(self) -> None:
        llm = FakeLlmCategorizer(LLM_RESULT)
        svc = self._make_service(
            rule_engine=FakeRuleEngine(None),
            ml=FailingMlCategorizer(),
            llm=llm,
        )

        output = svc.categorize(self._txn())

        assert output.result == LLM_RESULT
        assert llm.call_count == 1

    def test_llm_crash_falls_through_to_absolute_fallback(self) -> None:
        svc = self._make_service(
            rule_engine=FakeRuleEngine(None),
            llm=FailingLlmCategorizer(),
        )

        output = svc.categorize(self._txn())

        assert output.result.tier == CategorizationTier.FALLBACK

    def test_rules_only_no_ml_no_llm(self) -> None:
        svc = self._make_service(rule_engine=FakeRuleEngine(RULE_RESULT))

        output = svc.categorize(self._txn())

        assert output.result == RULE_RESULT

    def test_reference_id_none_for_import(self) -> None:
        svc = self._make_service(rule_engine=FakeRuleEngine(RULE_RESULT))
        txn = TransactionInput(description="test", amount=-10.0, reference_id=None)

        output = svc.categorize(txn)

        assert output.reference_id is None

    def test_all_tiers_crash_returns_fallback(self) -> None:
        svc = self._make_service(
            rule_engine=FailingRuleEngine(),
            ml=FailingMlCategorizer(),
            llm=FailingLlmCategorizer(),
        )

        output = svc.categorize(self._txn())

        assert output.result.tier == CategorizationTier.FALLBACK
        assert output.result.confidence == Confidence.LOW


# ──────────────────────────────────────────────
# Batch categorization
# ──────────────────────────────────────────────


class TestCategorizeBatch:
    def _make_txns(self, count: int) -> list[TransactionInput]:
        return [
            TransactionInput(description=f"txn-{i}", amount=-10.0 * (i + 1))
            for i in range(count)
        ]

    def test_all_resolved_by_rules(self) -> None:
        svc = CategorizationService(
            rule_engine=FakeRuleEngine(RULE_RESULT),
            fallback_subcategory_id=FALLBACK_SUBCAT_ID,
            fallback_category_id=FALLBACK_CAT_ID,
        )

        outputs = svc.categorize_batch(self._make_txns(5))

        assert len(outputs) == 5
        assert all(o.result.tier == CategorizationTier.RULE for o in outputs)

    def test_mixed_rule_and_fallback(self) -> None:
        class AlternatingRuleEngine:
            def __init__(self):
                self._call = 0

            def match(self, description: str, amount: float) -> CategorizationResult | None:
                self._call += 1
                if self._call % 2 == 1:
                    return RULE_RESULT
                return None

        svc = CategorizationService(
            rule_engine=AlternatingRuleEngine(),
            fallback_subcategory_id=FALLBACK_SUBCAT_ID,
            fallback_category_id=FALLBACK_CAT_ID,
        )

        outputs = svc.categorize_batch(self._make_txns(4))

        assert len(outputs) == 4
        assert outputs[0].result.tier == CategorizationTier.RULE
        assert outputs[1].result.tier == CategorizationTier.FALLBACK
        assert outputs[2].result.tier == CategorizationTier.RULE
        assert outputs[3].result.tier == CategorizationTier.FALLBACK

    def test_llm_batch_called_for_unresolved(self) -> None:
        llm = FakeLlmCategorizer(LLM_RESULT)
        svc = CategorizationService(
            rule_engine=FakeRuleEngine(None),
            fallback_subcategory_id=FALLBACK_SUBCAT_ID,
            fallback_category_id=FALLBACK_CAT_ID,
            llm_categorizer=llm,
        )

        outputs = svc.categorize_batch(self._make_txns(3))

        assert llm.batch_call_count == 1
        assert all(o.result.tier == CategorizationTier.LLM for o in outputs)

    def test_llm_batch_crash_falls_to_fallback(self) -> None:
        svc = CategorizationService(
            rule_engine=FakeRuleEngine(None),
            fallback_subcategory_id=FALLBACK_SUBCAT_ID,
            fallback_category_id=FALLBACK_CAT_ID,
            llm_categorizer=FailingLlmCategorizer(),
        )

        outputs = svc.categorize_batch(self._make_txns(3))

        assert all(o.result.tier == CategorizationTier.FALLBACK for o in outputs)

    def test_preserves_original_order(self) -> None:
        class EvenOnlyRuleEngine:
            def match(self, description: str, amount: float) -> CategorizationResult | None:
                idx = int(description.split("-")[1])
                if idx % 2 == 0:
                    return RULE_RESULT
                return None

        llm = FakeLlmCategorizer(LLM_RESULT)
        svc = CategorizationService(
            rule_engine=EvenOnlyRuleEngine(),
            fallback_subcategory_id=FALLBACK_SUBCAT_ID,
            fallback_category_id=FALLBACK_CAT_ID,
            llm_categorizer=llm,
        )
        txns = self._make_txns(4)

        outputs = svc.categorize_batch(txns)

        assert outputs[0].result.tier == CategorizationTier.RULE
        assert outputs[1].result.tier == CategorizationTier.LLM
        assert outputs[2].result.tier == CategorizationTier.RULE
        assert outputs[3].result.tier == CategorizationTier.LLM

    def test_empty_batch(self) -> None:
        svc = CategorizationService(
            rule_engine=FakeRuleEngine(None),
            fallback_subcategory_id=FALLBACK_SUBCAT_ID,
            fallback_category_id=FALLBACK_CAT_ID,
        )

        outputs = svc.categorize_batch([])

        assert outputs == []


# ──────────────────────────────────────────────
# CategorizationOutput
# ──────────────────────────────────────────────


class TestCategorizationOutput:
    def test_needs_review_when_low_confidence(self) -> None:
        output = CategorizationOutput.from_result(LLM_RESULT, reference_id=1)
        assert output.needs_review is True

    def test_no_review_when_high_confidence(self) -> None:
        output = CategorizationOutput.from_result(RULE_RESULT, reference_id=1)
        assert output.needs_review is False

    def test_reference_id_propagated(self) -> None:
        output = CategorizationOutput.from_result(RULE_RESULT, reference_id=42)
        assert output.reference_id == 42

    def test_reference_id_none(self) -> None:
        output = CategorizationOutput.from_result(RULE_RESULT)
        assert output.reference_id is None
