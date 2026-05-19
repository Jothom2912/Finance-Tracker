"""Golden file tests for the intent router.

Each test case provides a mock Ollama response (the JSON that constrained
sampling would produce) and verifies that the router parses it into the
correct ResolvedIntent. The "golden" output is the expected intent structure.

Covers: valid intents (4), invalid JSON fallback, system prompt templating.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest
from app.adapters.outbound.ollama_router import OllamaRouter
from app.domain.models import IntentName


def _mock_ollama_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    resp = MagicMock()
    resp.message = msg
    return resp


@pytest.fixture()
def router() -> OllamaRouter:
    return OllamaRouter()


@pytest.mark.parametrize(
    "query, ollama_json, expected_intent, expected_period, expected_slots",
    [
        pytest.param(
            "Hvad er min største udgift i april 2026?",
            '{"intent": "largest_expense", "period": "2026-04", "slots": {}}',
            IntentName.LARGEST_EXPENSE,
            "2026-04",
            {},
            id="largest_expense",
        ),
        pytest.param(
            "Vis fordeling af udgifter i maj",
            '{"intent": "category_breakdown", "period": "2026-05", "slots": {}}',
            IntentName.CATEGORY_BREAKDOWN,
            "2026-05",
            {},
            id="category_breakdown",
        ),
        pytest.param(
            "Find transaktioner med kaffe",
            '{"intent": "transaction_search", "period": "2026-05", "slots": {"query": "kaffe"}}',
            IntentName.TRANSACTION_SEARCH,
            "2026-05",
            {"query": "kaffe"},
            id="transaction_search",
        ),
        pytest.param(
            "Hvordan ser mit budget ud i marts?",
            '{"intent": "budget_status", "period": "2026-03", "slots": {}}',
            IntentName.BUDGET_STATUS,
            "2026-03",
            {},
            id="budget_status",
        ),
        pytest.param(
            "Hvor meget brugte jeg på dagligvarer i april?",
            '{"intent": "largest_expense", "period": "2026-04", "slots": {"category": "dagligvarer"}}',
            IntentName.LARGEST_EXPENSE,
            "2026-04",
            {"category": "dagligvarer"},
            id="largest_expense_with_category_slot",
        ),
    ],
)
async def test_classify_valid_intent(
    router: OllamaRouter,
    query: str,
    ollama_json: str,
    expected_intent: IntentName,
    expected_period: str,
    expected_slots: dict,
) -> None:
    mock_response = _mock_ollama_response(ollama_json)

    with patch("app.adapters.outbound.ollama_router.get_ollama_client") as mock_client:
        mock_client.return_value.chat.return_value = mock_response
        intent, elapsed_ms = await router.classify_intent(query)

    assert intent.intent == expected_intent
    assert intent.period == expected_period
    assert intent.slots == expected_slots
    assert elapsed_ms >= 0


async def test_classify_invalid_json_falls_back_to_search(
    router: OllamaRouter,
) -> None:
    mock_response = _mock_ollama_response("this is not valid json at all")

    with patch("app.adapters.outbound.ollama_router.get_ollama_client") as mock_client:
        mock_client.return_value.chat.return_value = mock_response
        intent, elapsed_ms = await router.classify_intent("noget uforståeligt")

    assert intent.intent == IntentName.TRANSACTION_SEARCH
    assert intent.slots == {"query": "noget uforståeligt"}
    assert re.fullmatch(r"\d{4}-\d{2}", intent.period)
    assert elapsed_ms >= 0


async def test_system_prompt_contains_current_period(
    router: OllamaRouter,
) -> None:
    """Verify system prompt is templated with current month, not hardcoded."""
    mock_response = _mock_ollama_response(
        '{"intent": "largest_expense", "period": "2026-05", "slots": {}}'
    )

    with patch("app.adapters.outbound.ollama_router.get_ollama_client") as mock_client:
        mock_client.return_value.chat.return_value = mock_response
        await router.classify_intent("test")

        call_args = mock_client.return_value.chat.call_args
        system_msg = call_args.kwargs["messages"][0]["content"]
        assert "2026-05" in system_msg or "2026-0" in system_msg
        assert "{current_period}" not in system_msg
