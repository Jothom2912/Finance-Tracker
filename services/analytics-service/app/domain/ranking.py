"""Reciprocal Rank Fusion (AI-20 hybrid search).

Ren utility: fusionerer rank-lister fra BM25 og kNN uden at kende til
ES. Klient-side fordi native RRF i ES 8.11 kræver licens over basic —
og en ren funktion er trivielt testbar, hvor en ES-DSL-klausul ikke er.

Score = Σ 1/(k + rank) over de lister dokumentet optræder i; k=60 er
litteraturens standardværdi (Cormack et al. 2009) og dæmper forskellen
mellem rank 1 og 2, så et dokument der er godt i BEGGE lister slår et
dokument der er suverænt i én.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")

RRF_K = 60


def rrf_fuse(rankings: Sequence[Sequence[T]], k: int = RRF_K) -> list[T]:
    """Fusionér rank-lister til én liste, bedste fusionerede score først.

    Deterministisk tiebreak: ved score-lighed vinder dokumentet med
    bedste placering i den først angivne liste (BM25 per konvention).
    """
    scores: dict[T, float] = {}
    first_seen: dict[T, tuple[int, int]] = {}

    for list_idx, ranking in enumerate(rankings):
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
            if item not in first_seen:
                first_seen[item] = (list_idx, rank)

    return sorted(scores, key=lambda item: (-scores[item], first_seen[item]))
