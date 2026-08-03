"""Pinned TAX-07 legacy proposal registry owned by categorization-service."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from contracts.reclassification import Disposition

from app.domain.taxonomy_definitions import SEED_VERSION, SUBCATEGORY_KEYS, TAXONOMY_KEYS
from app.domain.taxonomy_identity import TAXONOMY_PUBLIC_IDS

MAPPING_VERSION = "tax07-2026-08-01-v1"


@dataclass(frozen=True, slots=True)
class LegacyProposal:
    legacy_id: int
    disposition: Disposition
    reason_code: str
    target_keys: tuple[str, ...]


_SAFE_CATEGORY_TARGETS = {
    1: "food_drink",
    2: "housing",
    3: "transport",
    4: "leisure_experiences",
    9: "income",
    10: "transfers_wealth",
}
_REVIEW_CATEGORY_TARGETS = {
    5: ("health_personal_care", "shopping"),
    6: ("housing", "shopping"),
    7: ("financial_costs", "transfers_wealth"),
    8: ("other_income", "unknown_transfer"),
}

CATEGORY_PROPOSALS = tuple(
    LegacyProposal(legacy_id, Disposition.SAFE_ONE_TO_ONE, "direct_parent_mapping", (target,))
    for legacy_id, target in _SAFE_CATEGORY_TARGETS.items()
) + tuple(
    LegacyProposal(legacy_id, Disposition.MANUAL_REVIEW, "split_parent_requires_child", targets)
    for legacy_id, targets in _REVIEW_CATEGORY_TARGETS.items()
)

_SAFE_SUBCATEGORY_TARGETS = {
    1: "groceries",
    2: "restaurant_cafe",
    3: "takeaway",
    4: "restaurant_cafe",
    5: "kiosk",
    6: "rent",
    7: "home_utilities",
    8: "insurance",
    9: "mobile_internet",
    10: "home_maintenance",
    11: "public_transport",
    12: "fuel_charging",
    13: "vehicle_service",
    14: "parking_tolls",
    15: "cycling_micromobility",
    17: "bar_nightlife",
    19: "sport_fitness",
    22: "hairdresser",
    23: "pharmacy_medicine",
    24: "clothing_footwear",
    26: "electronics",
    28: "interest_expense",
    29: "investment",
    30: "cash_withdrawal",
    31: "services_unspecified",
    33: "salary",
    34: "public_benefits",
    36: "capital_income",
}
_EVIDENCE_SUBCATEGORY_TARGETS = {
    16: ("digital_services", "memberships", "services_unspecified"),
    18: ("culture_events", "gaming_hobby", "leisure_unspecified"),
    20: ("sport_fitness", "clothing_footwear", "shopping_unspecified"),
    21: ("personal_care", "health_care_unspecified"),
    25: ("furniture_homeware", "hardware_diy"),
    27: ("bank_fees", "loan_fx_fees", "financial_costs_unspecified"),
    32: ("other_income", "unknown_transfer"),
    35: ("person_transfer", "other_income", "refund"),
    37: ("own_accounts_savings", "unknown_transfer"),
    38: ("person_transfer", "unknown_transfer"),
    39: ("person_transfer", "unknown_transfer"),
    40: ("own_accounts_savings", "person_transfer", "unknown_transfer"),
    41: ("own_accounts_savings", "unknown_transfer"),
}

SUBCATEGORY_PROPOSALS = tuple(
    LegacyProposal(legacy_id, Disposition.SAFE_ONE_TO_ONE, "direct_leaf_mapping", (target,))
    for legacy_id, target in _SAFE_SUBCATEGORY_TARGETS.items()
) + tuple(
    LegacyProposal(legacy_id, Disposition.EVIDENCE_PROPOSAL, "split_leaf_requires_evidence", targets)
    for legacy_id, targets in _EVIDENCE_SUBCATEGORY_TARGETS.items()
)


def mapping_payload() -> dict[str, object]:
    def serialize(proposal: LegacyProposal) -> dict[str, object]:
        value = asdict(proposal)
        value["disposition"] = proposal.disposition.value
        value["targets"] = [{"key": key, "public_id": TAXONOMY_PUBLIC_IDS[key]} for key in proposal.target_keys]
        value.pop("target_keys")
        return value

    return {
        "mapping_version": MAPPING_VERSION,
        "taxonomy_version": SEED_VERSION,
        "categories": [serialize(item) for item in sorted(CATEGORY_PROPOSALS, key=lambda item: item.legacy_id)],
        "subcategories": [serialize(item) for item in sorted(SUBCATEGORY_PROPOSALS, key=lambda item: item.legacy_id)],
    }


def mapping_bytes() -> bytes:
    return (json.dumps(mapping_payload(), sort_keys=True, separators=(",", ":")) + "\n").encode()


def mapping_sha256() -> str:
    return hashlib.sha256(mapping_bytes()).hexdigest()


def validate_mapping() -> None:
    if {item.legacy_id for item in CATEGORY_PROPOSALS} != set(range(1, 11)):
        raise ValueError("mapping must cover legacy categories 1..10 exactly once")
    if {item.legacy_id for item in SUBCATEGORY_PROPOSALS} != set(range(1, 42)):
        raise ValueError("mapping must cover legacy subcategories 1..41 exactly once")
    if any(
        len(item.target_keys) != 1 for item in SUBCATEGORY_PROPOSALS if item.disposition == Disposition.SAFE_ONE_TO_ONE
    ):
        raise ValueError("safe mappings must have exactly one target")
    if any(
        len(item.target_keys) == 1
        for item in SUBCATEGORY_PROPOSALS
        if item.disposition == Disposition.EVIDENCE_PROPOSAL
    ):
        raise ValueError("split mappings cannot be marked safe")
    target_keys = {key for item in CATEGORY_PROPOSALS + SUBCATEGORY_PROPOSALS for key in item.target_keys}
    if not target_keys <= TAXONOMY_KEYS:
        raise ValueError("mapping contains a target outside the active taxonomy registry")
    if not {key for item in SUBCATEGORY_PROPOSALS for key in item.target_keys} <= SUBCATEGORY_KEYS:
        raise ValueError("subcategory mapping must resolve to active leaves")


validate_mapping()
