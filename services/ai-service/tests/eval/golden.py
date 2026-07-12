"""Golden set for the eval harness (AI-01) — ~50 Danish cases in three groups.

- RETRIEVAL_CASES: question → the fixture transaction ids a good retriever
  should surface (recall@k / MRR in test_retrieval_eval.py).
- INTENT_CASES: question → the intent the router must pick
  (accuracy in test_intent_eval.py).
- AGGREGATION_CASES: question → the numerically exact answer computed from the
  fixture data. These document the "aggregation must never come from top-K
  vectors" contract (AI-03/AI-19); the literals are drift-guarded against
  fixtures.py by test_golden_selfcheck.py, and the cases double as input for a
  future end-to-end numeric-correctness eval against live backends.

All expected values derive from tests/eval/fixtures.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievalCase:
    question: str
    relevant_ids: frozenset[int]
    period: str | None = None


@dataclass(frozen=True)
class IntentCase:
    question: str
    expected_intent: str


@dataclass(frozen=True)
class AggregationCase:
    question: str
    expected_value: float
    # (category, year_month, tx_type, description) selectors that reproduce the
    # value from fixtures — used by the self-check. None = don't filter.
    category: str | None = None
    year_month: str | None = None
    tx_type: str = "expense"
    description: str | None = None
    kind: str = "sum"  # sum | count | max
    notes: str = field(default="", compare=False)


RETRIEVAL_CASES: list[RetrievalCase] = [
    # Eksakt merchant (leksikalsk-formede spørgsmål — AI-06/AI-20-følsomme)
    RetrievalCase("Netto", frozenset({1, 5, 7})),
    RetrievalCase("Foetex", frozenset({2})),
    RetrievalCase("McDonalds", frozenset({10})),
    RetrievalCase("Netflix", frozenset({30, 31, 32})),
    RetrievalCase("MobilePay", frozenset({72})),
    # Kategori/emne-formuleringer (semantisk)
    RetrievalCase("dagligvarer indkoeb supermarked", frozenset({1, 2, 3, 4, 5, 6, 7, 8})),
    RetrievalCase("kaffe", frozenset({12, 13, 14})),
    RetrievalCase("restauranter og cafeer", frozenset({10, 11, 12, 13, 14, 15})),
    RetrievalCase("streaming abonnementer", frozenset({30, 31, 32, 33, 34, 35, 36})),
    RetrievalCase("tog pendlerkort offentlig transport", frozenset({20, 21, 22, 23})),
    RetrievalCase("benzin tankstation", frozenset({24})),
    RetrievalCase("husleje", frozenset({50, 51, 52})),
    RetrievalCase("el og vand regninger", frozenset({53, 54})),
    RetrievalCase("toej shopping", frozenset({40, 41, 42})),
    RetrievalCase("fitnesscenter traening", frozenset({62, 63, 64})),
    RetrievalCase("apotek medicin", frozenset({60})),
    RetrievalCase("loen indkomst", frozenset({70, 71})),
    # Periode-filtrerede (metadata-filter + semantik sammen)
    RetrievalCase("dagligvarer", frozenset({1, 2, 8}), period="2026-04"),
    RetrievalCase("Netflix", frozenset({32}), period="2026-05"),
    RetrievalCase("restaurant", frozenset({13, 14}), period="2026-05"),
]

INTENT_CASES: list[IntentCase] = [
    IntentCase("Hvad er min største udgift i april?", "largest_expense"),
    IntentCase("Hvad var min største udgift sidste måned?", "largest_expense"),
    IntentCase("Hvilken enkelt betaling var størst i marts?", "largest_expense"),
    IntentCase("Hvordan fordeler mine udgifter sig på kategorier?", "category_breakdown"),
    IntentCase("Hvor stor en andel af mit forbrug går til hver kategori?", "category_breakdown"),
    IntentCase("Vis min kategorifordeling for maj", "category_breakdown"),
    IntentCase("Hvordan går det med mit budget?", "budget_status"),
    IntentCase("Er jeg over budget denne måned?", "budget_status"),
    IntentCase("Hvor meget har jeg tilbage af mit budget?", "budget_status"),
    IntentCase("Hvad bruger jeg på mad?", "transaction_search"),
    IntentCase("Vis mine Netto-køb", "transaction_search"),
    IntentCase("Hvor meget går til kaffe?", "transaction_search"),
    IntentCase("Find transaktioner fra DSB", "transaction_search"),
    IntentCase("Hvad har jeg brugt på streaming?", "transaction_search"),
    IntentCase("Største udgift på mad i maj", "transaction_search"),
    IntentCase("Hvor meget brugte jeg på restauranter i marts?", "transaction_search"),
]

AGGREGATION_CASES: list[AggregationCase] = [
    AggregationCase(
        "Hvor meget brugte jeg på dagligvarer i april?",
        967.30,
        category="Dagligvarer",
        year_month="2026-04",
    ),
    AggregationCase(
        "Hvor meget brugte jeg på dagligvarer i marts?",
        1014.25,
        category="Dagligvarer",
        year_month="2026-03",
    ),
    AggregationCase(
        "Hvad kostede restaurantbesøg i april i alt?",
        400.00,
        category="Restaurant",
        year_month="2026-04",
    ),
    AggregationCase(
        "Hvad brugte jeg i alt i april?",
        10851.30,
        year_month="2026-04",
    ),
    AggregationCase(
        "Hvad brugte jeg i alt i maj?",
        9942.10,
        year_month="2026-05",
    ),
    AggregationCase(
        "Hvor meget tjente jeg i april?",
        29700.00,
        year_month="2026-04",
        tx_type="income",
    ),
    AggregationCase(
        "Hvad var min største udgift i april?",
        6500.00,
        year_month="2026-04",
        kind="max",
        notes="Husleje (id 51) — AI-19: skal komme fra ES-sort, aldrig top-K vektorer",
    ),
    AggregationCase(
        "Hvad var min største udgift i maj?",
        6500.00,
        year_month="2026-05",
        kind="max",
    ),
    AggregationCase(
        "Hvor meget brugte jeg på transport i april?",
        470.00,
        category="Transport",
        year_month="2026-04",
    ),
    AggregationCase(
        "Hvor mange gange handlede jeg i Netto?",
        3,
        description="Netto",
        kind="count",
    ),
    AggregationCase(
        "Hvad har jeg brugt hos Netto i alt?",
        720.15,
        description="Netto",
    ),
    AggregationCase(
        "Hvor meget brugte jeg på underholdning i april?",
        367.00,
        category="Underholdning",
        year_month="2026-04",
    ),
    AggregationCase(
        "Hvad koster mit fitnessabonnement om måneden?",
        249.00,
        description="Fitness World",
        kind="max",
        notes="konstant pr. måned",
    ),
    AggregationCase(
        "Hvor meget brugte jeg på bolig i april?",
        7343.00,
        category="Bolig",
        year_month="2026-04",
    ),
]
