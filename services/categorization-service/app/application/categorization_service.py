"""CategorizationService — pipeline orchestrator.

Runs tiers in order: rules -> ML -> LLM -> fallback.
Each tier failure is isolated — never crashes the pipeline.
ML and LLM are optional; the system works with rules alone.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from typing import Optional

from app.application.dto import CategorizeRequestDTO, CategorizeResponseDTO
from app.application.ports.outbound import ILlmCategorizer, IMlCategorizer, IRuleEngine
from app.domain.value_objects import CategorizationResult, CategorizationTier, Confidence

logger = logging.getLogger(__name__)


class CategorizationService:
    """Pipeline orchestrator.

    Tiers run in order.  Each tier can:
      - Return a result (pipeline stops)
      - Return None (next tier tries)
      - Raise an exception (logged, next tier tries)
    """

    def __init__(
        self,
        rule_engine: IRuleEngine,
        fallback_subcategory_id: int,
        fallback_category_id: int,
        ml_categorizer: Optional[IMlCategorizer] = None,
        llm_categorizer: Optional[ILlmCategorizer] = None,
    ):
        self._rule_engine = rule_engine
        self._ml = ml_categorizer
        self._llm = llm_categorizer
        self._fallback_subcategory_id = fallback_subcategory_id
        self._fallback_category_id = fallback_category_id

    async def categorize(self, request: CategorizeRequestDTO) -> CategorizeResponseDTO:
        """Categorize a single transaction (sync, tier 1 only for now)."""
        result = self._run_pipeline(request)
        return self._to_response(result)

    async def categorize_batch(
        self,
        requests: list[CategorizeRequestDTO],
    ) -> list[CategorizeResponseDTO]:
        """Batch categorization — rule engine on all, then ML/LLM on remainder."""
        return [await self.categorize(r) for r in requests]

    def _run_pipeline(self, request: CategorizeRequestDTO) -> CategorizationResult:
        description = request.description
        amount = request.amount
        evidence = (request.merchant, request.counterparty, request.provider, request.country)
        if any(value is not None for value in evidence):
            match_rule = partial(
                self._rule_engine.match,
                description,
                amount,
                merchant=request.merchant,
                counterparty=request.counterparty,
                provider=request.provider,
                country=request.country,
            )
        else:
            match_rule = partial(self._rule_engine.match, description, amount)
        result = self._try_tier("rules", match_rule)
        if result is not None:
            return result

        # Bind the tier locally before closing over it. `if self._ml is not None`
        # does not narrow inside a lambda, because the lambda captures `self` and
        # runs later, inside _try_tier — where an AttributeError would be swallowed
        # as "tier failed" rather than surfacing.
        ml = self._ml
        if ml is not None:
            result = self._try_tier(
                "ml",
                lambda: ml.predict(description),
            )
            if result is not None:
                return result

        llm = self._llm
        if llm is not None:
            result = self._try_tier(
                "llm",
                lambda: llm.predict(description, amount),
            )
            if result is not None:
                return result

        logger.warning("All categorization tiers exhausted; using fallback")
        return self._absolute_fallback()

    def _try_tier(
        self,
        tier_name: str,
        fn: Callable[[], CategorizationResult | None],
    ) -> CategorizationResult | None:
        try:
            result = fn()
            if result is not None:
                logger.debug(
                    "Tier '%s' matched subcategory %d [%s]",
                    tier_name,
                    result.subcategory_id,
                    result.confidence.value,
                )
            return result
        except Exception:
            logger.exception("Categorization tier '%s' failed", tier_name)
            return None

    def _absolute_fallback(self) -> CategorizationResult:
        return CategorizationResult(
            category_id=self._fallback_category_id,
            subcategory_id=self._fallback_subcategory_id,
            tier=CategorizationTier.FALLBACK,
            confidence=Confidence.LOW,
        )

    @staticmethod
    def _to_response(result: CategorizationResult) -> CategorizeResponseDTO:
        return CategorizeResponseDTO(
            category_id=result.category_id,
            subcategory_id=result.subcategory_id,
            merchant_id=result.merchant_id,
            tier=result.tier.value,
            confidence=result.confidence.value,
            needs_review=result.needs_review,
        )
