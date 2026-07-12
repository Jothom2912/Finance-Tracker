"""Drift-guard: the golden literals must be reproducible from fixtures.py.

Runs in the normal unit suite (no Ollama, not marked `eval`) — if someone
edits the fixture dataset, this pinpoints exactly which golden cases drifted.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .fixtures import EVAL_TRANSACTIONS
from .golden import AGGREGATION_CASES, INTENT_CASES, RETRIEVAL_CASES, AggregationCase

KNOWN_INTENTS = {"largest_expense", "category_breakdown", "transaction_search", "budget_status"}

ALL_FIXTURE_IDS = {t.id for t in EVAL_TRANSACTIONS}


def _select(case: AggregationCase) -> list[Decimal]:
    amounts = []
    for t in EVAL_TRANSACTIONS:
        if case.tx_type and t.transaction_type != case.tx_type:
            continue
        if case.category and t.category_name != case.category:
            continue
        if case.year_month and t.date.strftime("%Y-%m") != case.year_month:
            continue
        if case.description and t.description != case.description:
            continue
        amounts.append(abs(t.amount))
    return amounts


@pytest.mark.parametrize("case", AGGREGATION_CASES, ids=lambda c: c.question)
def test_aggregation_literal_matches_fixture_computation(case: AggregationCase) -> None:
    amounts = _select(case)
    assert amounts, f"selector matched no fixture rows: {case}"

    if case.kind == "sum":
        computed = float(sum(amounts))
    elif case.kind == "count":
        computed = len(amounts)
    elif case.kind == "max":
        computed = float(max(amounts))
    else:
        pytest.fail(f"unknown kind {case.kind!r}")

    assert computed == pytest.approx(case.expected_value, abs=0.01), (
        f"{case.question!r}: golden={case.expected_value}, fixtures give {computed}"
    )


@pytest.mark.parametrize("case", RETRIEVAL_CASES, ids=lambda c: f"{c.question}|{c.period}")
def test_retrieval_relevant_ids_exist_in_fixtures(case) -> None:
    missing = case.relevant_ids - ALL_FIXTURE_IDS
    assert not missing, f"{case.question!r} references unknown fixture ids: {missing}"

    if case.period:
        for t in EVAL_TRANSACTIONS:
            if t.id in case.relevant_ids:
                assert t.date.strftime("%Y-%m") == case.period, (
                    f"{case.question!r}: id {t.id} is outside period {case.period}"
                )


def test_intent_cases_use_known_intents() -> None:
    unknown = {c.expected_intent for c in INTENT_CASES} - KNOWN_INTENTS
    assert not unknown
