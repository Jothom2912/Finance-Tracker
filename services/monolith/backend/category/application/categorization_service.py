"""
CategorizationService — pipeline orchestrator.

Runs tiers in order: rules -> ML -> LLM.
Each tier failure is isolated — never crashes the pipeline.
ML and LLM are optional; the system works with rules alone.

Ports (IRuleEngine, IMlCategorizer, ILlmCategorizer) are defined in
  category/application/ports/outbound.py
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from backend.category.application.ports.outbound import (
    ILlmCategorizer,
    IMlCategorizer,
    IRuleEngine,
)
from backend.category.domain.value_objects import (
    CategorizationResult,
    CategorizationTier,
    Confidence,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Input/Output DTOs
# ──────────────────────────────────────────────


@dataclass
class TransactionInput:
    """Input to categorization — the minimum we need.

    reference_id is optional: set to transaction_id for existing rows,
    None during CSV import (transaction doesn't exist yet).
    Batch method uses list-index internally, not reference_id.
    """

    description: str
    amount: float
    reference_id: int | None = None


@dataclass
class CategorizationOutput:
    """Output from orchestrator — result + review flag."""

    result: CategorizationResult
    needs_review: bool
    reference_id: int | None = None

    @staticmethod
    def from_result(
        result: CategorizationResult, reference_id: int | None = None
    ) -> CategorizationOutput:
        return CategorizationOutput(
            result=result,
            needs_review=result.confidence == Confidence.LOW,
            reference_id=reference_id,
        )


# ──────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────


class CategorizationService:
    """
    Pipeline orchestrator.

    Tiers run in order. Each tier can:
      - Return a result (pipeline stops)
      - Return None (next tier tries)
      - Raise an exception (logged, next tier tries)

    ML and LLM are optional — with only rule engine the system
    still works, just with more "Anden" categorizations.
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

    def categorize(self, txn: TransactionInput) -> CategorizationOutput:
        """
        Categorize a single transaction.

        Flow: rules -> ML -> LLM -> absolute fallback ("Anden").
        """
        desc_short = txn.description[:40]

        result = self._try_tier(
            "rules", desc_short,
            lambda: self._rule_engine.match(txn.description, txn.amount),
        )
        if result is not None:
            return CategorizationOutput.from_result(result, txn.reference_id)

        if self._ml is not None:
            result = self._try_tier(
                "ml", desc_short,
                lambda: self._ml.predict(txn.description),
            )
            if result is not None:
                return CategorizationOutput.from_result(result, txn.reference_id)

        if self._llm is not None:
            result = self._try_tier(
                "llm", desc_short,
                lambda: self._llm.predict(txn.description, txn.amount),
            )
            if result is not None:
                return CategorizationOutput.from_result(result, txn.reference_id)

        logger.warning(
            "All tiers exhausted for '%s'. Using fallback.", desc_short,
        )
        return CategorizationOutput.from_result(
            self._absolute_fallback(), txn.reference_id
        )

    def categorize_batch(
        self, transactions: list[TransactionInput]
    ) -> list[CategorizationOutput]:
        """
        Batch categorization — optimized for CSV import.

        Strategy:
          1. Run rule engine on all transactions (cheap)
          2. Run ML on unmatched remainder (cheap)
          3. Collect LLM fallbacks and send as batch (expensive, done in bulk)

        Uses list-index as key (not reference_id) to avoid
        duplicate issues during import where reference_id is None.
        """
        count = len(transactions)
        results: list[CategorizationOutput | None] = [None] * count
        remaining_indices: list[int] = list(range(count))

        # Tier 1: Rule engine (all)
        still_remaining: list[int] = []
        for idx in remaining_indices:
            txn = transactions[idx]
            result = self._try_tier(
                "rules", txn.description[:40],
                lambda t=txn: self._rule_engine.match(t.description, t.amount),
            )
            if result is not None:
                results[idx] = CategorizationOutput.from_result(
                    result, txn.reference_id
                )
            else:
                still_remaining.append(idx)
        remaining_indices = still_remaining

        logger.info(
            "Batch tier 1 (rules): %d/%d resolved, %d remaining",
            count - len(remaining_indices), count, len(remaining_indices),
        )

        if not remaining_indices:
            return results  # type: ignore[return-value]

        # Tier 2: ML (remaining)
        if self._ml is not None:
            still_remaining = []
            for idx in remaining_indices:
                txn = transactions[idx]
                result = self._try_tier(
                    "ml", txn.description[:40],
                    lambda t=txn: self._ml.predict(t.description),
                )
                if result is not None:
                    results[idx] = CategorizationOutput.from_result(
                        result, txn.reference_id
                    )
                else:
                    still_remaining.append(idx)
            remaining_indices = still_remaining

            logger.info(
                "Batch tier 2 (ML): %d/%d total resolved, %d remaining",
                count - len(remaining_indices), count, len(remaining_indices),
            )

        if not remaining_indices:
            return results  # type: ignore[return-value]

        # Tier 3: LLM batch (remaining)
        if self._llm is not None and remaining_indices:
            llm_inputs = [
                (transactions[idx].description, transactions[idx].amount)
                for idx in remaining_indices
            ]
            try:
                llm_results = self._llm.predict_batch(llm_inputs)
                for idx, llm_result in zip(remaining_indices, llm_results):
                    results[idx] = CategorizationOutput.from_result(
                        llm_result, transactions[idx].reference_id
                    )
                remaining_indices = []
                logger.info(
                    "Batch tier 3 (LLM): %d/%d total resolved", count, count,
                )
            except Exception:
                logger.exception("LLM batch prediction failed")

        # Fallback for anything still unresolved
        for idx in remaining_indices:
            results[idx] = CategorizationOutput.from_result(
                self._absolute_fallback(), transactions[idx].reference_id
            )

        return results  # type: ignore[return-value]

    # ──────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────

    def _try_tier(
        self,
        tier_name: str,
        context: str,
        fn: Callable[[], CategorizationResult | None],
    ) -> CategorizationResult | None:
        """Run one tier with error isolation."""
        try:
            result = fn()
            if result is not None:
                logger.debug(
                    "Tier '%s' matched '%s' -> subcategory %d [%s]",
                    tier_name,
                    context,
                    result.subcategory_id,
                    result.confidence.value,
                )
            return result
        except Exception:
            logger.exception(
                "Tier '%s' failed for '%s'", tier_name, context,
            )
            return None

    def _absolute_fallback(self) -> CategorizationResult:
        """Last resort — 'Anden' with LOW confidence."""
        return CategorizationResult(
            category_id=self._fallback_category_id,
            subcategory_id=self._fallback_subcategory_id,
            tier=CategorizationTier.FALLBACK,
            confidence=Confidence.LOW,
        )
