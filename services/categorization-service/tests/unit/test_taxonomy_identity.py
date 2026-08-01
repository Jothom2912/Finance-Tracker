from __future__ import annotations

from uuid import UUID

from app.domain.taxonomy_definitions import TAXONOMY_DEFINITIONS
from app.domain.taxonomy_identity import TAXONOMY_PUBLIC_IDS, TAXONOMY_VERSION


def test_registry_covers_all_80_nodes_with_unique_uuid7_values() -> None:
    assert TAXONOMY_VERSION == 1
    assert len(TAXONOMY_PUBLIC_IDS) == len(TAXONOMY_DEFINITIONS) == 80
    assert len(set(TAXONOMY_PUBLIC_IDS.values())) == 80
    assert {UUID(value).version for value in TAXONOMY_PUBLIC_IDS.values()} == {7}


def test_registry_is_stable_for_known_keys() -> None:
    assert TAXONOMY_PUBLIC_IDS["food_drink"] == "019fba9e-d800-7d31-8208-aeddb2226b0f"
    assert TAXONOMY_PUBLIC_IDS["unknown_transfer"] == "019fba9e-d800-726b-bb7b-231de242ca95"
