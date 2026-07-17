"""Retrieval quality eval (AI-01): recall@k + MRR over the golden set.

Baseline (ChromaDB + bge-m3) is the yardstick every retrieval change —
hybrid search, reranking, the AI-20 ES cutover — must beat or match.
Floors below are set just under the measured 2026-07-12 baseline so
regressions fail loudly; raise them when a change lifts the metrics.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pytest
from app.application.ports.semantic_search_port import ISemanticSearchPort

from .fixtures import EVAL_USER_ID, OTHER_USER_ID
from .golden import RETRIEVAL_CASES, RetrievalCase

logger = logging.getLogger(__name__)

SearchFactory = Callable[[int], ISemanticSearchPort]

pytestmark = pytest.mark.eval

TOP_K = 10
K_STRICT = 3

# Baseline 2026-07-13 (ChromaDB + bge-m3, distractor-korpus ~67 docs, 35 cases):
# mean recall@10 = 1.000, mean recall@3 = 0.967, mean MRR = 0.981.
# ES hybrid målt 2026-07-14 (cutover-gaten): recall@10 = 0.996,
# recall@3 = 0.971, MRR = 0.967 — bedre på den skarpe metrik; MRR-tabet
# er én case ("toej shopping", hvor BM25 matcher Shopping-KATEGORIEN
# leksikalsk; AI-21 kategori-resolve er modtrækket). Cutover udført.
# Floors ligger lige under målt baseline så regressioner fejler højt
# (ét fuldt case-drop koster ~0.029 i mean); hæv dem når en ændring
# løfter metrikken.
MEAN_RECALL_FLOOR = 0.95
MEAN_MRR_FLOOR = 0.95
MEAN_RECALL_STRICT_FLOOR = 0.95


def _run_case(case: RetrievalCase, search_factory: SearchFactory) -> tuple[float, float, float]:
    """Returns (recall@TOP_K, recall@K_STRICT, reciprocal rank) for one case."""
    search = search_factory(EVAL_USER_ID)
    items, _ = search.search(case.question, period=case.period, top_k=TOP_K)
    retrieved = [i.id for i in items]

    hits = case.relevant_ids.intersection(retrieved)
    recall = len(hits) / min(len(case.relevant_ids), TOP_K)

    strict_hits = case.relevant_ids.intersection(retrieved[:K_STRICT])
    recall_strict = len(strict_hits) / min(len(case.relevant_ids), K_STRICT)

    rr = 0.0
    for rank, txn_id in enumerate(retrieved, start=1):
        if txn_id in case.relevant_ids:
            rr = 1.0 / rank
            break
    return recall, recall_strict, rr


def test_retrieval_golden_set(search_factory: SearchFactory) -> None:
    rows = []
    for case in RETRIEVAL_CASES:
        recall, recall_strict, rr = _run_case(case, search_factory)
        rows.append((case, recall, recall_strict, rr))

    print("\n--- Retrieval eval (backend=es-hybrid) ---")
    print(f"{'question':<45} {'period':<9} {'recall@10':>9} {'recall@3':>9} {'RR':>6}")
    for case, recall, recall_strict, rr in sorted(rows, key=lambda r: (r[2], r[1])):
        print(f"{case.question:<45} {case.period or '-':<9} {recall:>9.2f} {recall_strict:>9.2f} {rr:>6.2f}")

    n = len(rows)
    mean_recall = sum(r for _, r, _, _ in rows) / n
    mean_strict = sum(s for _, _, s, _ in rows) / n
    mean_mrr = sum(rr for _, _, _, rr in rows) / n
    print(
        f"\nmean recall@{TOP_K}: {mean_recall:.3f}   mean recall@{K_STRICT}: {mean_strict:.3f}   "
        f"mean MRR: {mean_mrr:.3f}   cases: {n}"
    )

    assert mean_recall >= MEAN_RECALL_FLOOR, f"mean recall@{TOP_K} {mean_recall:.3f} under floor {MEAN_RECALL_FLOOR}"
    assert mean_strict >= MEAN_RECALL_STRICT_FLOOR, (
        f"mean recall@{K_STRICT} {mean_strict:.3f} under floor {MEAN_RECALL_STRICT_FLOOR}"
    )
    assert mean_mrr >= MEAN_MRR_FLOOR, f"mean MRR {mean_mrr:.3f} under floor {MEAN_MRR_FLOOR}"


def test_tenant_isolation_no_cross_user_results(search_factory: SearchFactory) -> None:
    """User 9001's queries must never surface user 9002's documents (and v.v.)."""
    own = search_factory(EVAL_USER_ID)
    other = search_factory(OTHER_USER_ID)

    items_own, _ = own.search("dagligvarer Bilka McDonalds", top_k=50)
    items_other, _ = other.search("dagligvarer Bilka McDonalds", top_k=50)

    other_ids = {900, 901}
    assert not other_ids.intersection({i.id for i in items_own})
    assert {i.id for i in items_other} <= other_ids
    assert items_other  # user 9002 kan se sine egne
