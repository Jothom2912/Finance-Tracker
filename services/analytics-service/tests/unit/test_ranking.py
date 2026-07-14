"""RRF-fusion: ren rank-matematik (AI-20)."""

from __future__ import annotations

from app.domain.ranking import rrf_fuse


def test_document_in_both_lists_beats_single_list_winner() -> None:
    # "b" er nr. 2 i begge lister; "a" og "c" er nr. 1 i hver sin.
    # RRF: b = 2/62 > a = 1/61 + 0 — konsensus slår solo-toppen.
    fused = rrf_fuse([["a", "b", "x"], ["c", "b", "y"]])
    assert fused[0] == "b"
    assert set(fused[:3]) == {"a", "b", "c"}


def test_single_list_degrades_to_identity() -> None:
    assert rrf_fuse([["a", "b", "c"]]) == ["a", "b", "c"]


def test_empty_rankings() -> None:
    assert rrf_fuse([]) == []
    assert rrf_fuse([[], []]) == []


def test_tiebreak_is_deterministic_first_list_wins() -> None:
    # Symmetriske placeringer → samme score; tiebreak = bedste placering
    # i første liste (BM25 per konvention).
    fused = rrf_fuse([["a", "b"], ["b", "a"]])
    assert fused == ["a", "b"]


def test_disjoint_lists_interleave_by_rank() -> None:
    fused = rrf_fuse([["a1", "a2"], ["b1", "b2"]])
    assert fused == ["a1", "b1", "a2", "b2"]
