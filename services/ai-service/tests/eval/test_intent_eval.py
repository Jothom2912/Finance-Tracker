"""Router intent-classification eval (AI-01): accuracy over the golden set.

Gates router-prompt changes (AI-02 slot activation, AI-08 query rewriting,
AI-13 confidence) — compare accuracy before/after any prompt edit.
"""

from __future__ import annotations

import pytest
from app.adapters.outbound.ollama_router import OllamaRouter

from .golden import INTENT_CASES

pytestmark = pytest.mark.eval

# Baseline 2026-07-12 (qwen3:4b, constrained JSON): accuracy 1.000 (16/16).
# Margin for LLM-nondeterminisme ved temp 0.1; hæv ikke over 0.95.
ACCURACY_FLOOR = 0.90


async def test_router_intent_accuracy(router_model: str) -> None:
    router = OllamaRouter()
    results = []

    for case in INTENT_CASES:
        # Én retry: Ollamas model-runner kan dø transient ("unexpected EOF")
        # under ressourcepres — det er infra, ikke en router-miss.
        try:
            resolved, _ = await router.classify_intent(case.question)
        except Exception:
            resolved, _ = await router.classify_intent(case.question)
        results.append((case, resolved.intent.value))

    print("\n--- Intent eval (qwen3:4b baseline) ---")
    wrong = [(c, got) for c, got in results if got != c.expected_intent]
    for case, got in wrong:
        print(f"MISS: {case.question!r} -> {got} (expected {case.expected_intent})")

    accuracy = (len(results) - len(wrong)) / len(results)
    print(f"accuracy: {accuracy:.3f} ({len(results) - len(wrong)}/{len(results)})")

    assert accuracy >= ACCURACY_FLOOR, f"intent accuracy {accuracy:.3f} under floor {ACCURACY_FLOOR}"
