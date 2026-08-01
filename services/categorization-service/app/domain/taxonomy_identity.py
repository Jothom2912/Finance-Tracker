"""Pinned canonical identity registry for the TAX-06 taxonomy snapshot."""

from __future__ import annotations

import hashlib
import uuid

from app.domain.taxonomy_definitions import SEED_VERSION, TAXONOMY_DEFINITIONS

TAXONOMY_VERSION = 1
_PINNED_UNIX_MS = 1_785_542_400_000  # 2026-08-01T00:00:00Z


def _pinned_uuid7(semantic_key: str) -> str:
    """Build a stable UUIDv7 from the approved snapshot timestamp and key.

    The values are deterministic so migrations, fixtures and repair events share one
    registry.  The timestamp/version/variant bits follow RFC 9562; hash bits merely pin
    the once-approved random portion and are not used to derive business meaning.
    """
    digest = int.from_bytes(hashlib.sha256(f"{SEED_VERSION}:{semantic_key}".encode()).digest()[:10], "big")
    value = (_PINNED_UNIX_MS & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= (digest >> 68 & 0xFFF) << 64
    value |= 0b10 << 62
    value |= digest & ((1 << 62) - 1)
    return str(uuid.UUID(int=value))


TAXONOMY_PUBLIC_IDS = {
    definition.semantic_key: _pinned_uuid7(definition.semantic_key) for definition in TAXONOMY_DEFINITIONS
}


def validate_taxonomy_identity_registry() -> None:
    keys = {definition.semantic_key for definition in TAXONOMY_DEFINITIONS}
    if set(TAXONOMY_PUBLIC_IDS) != keys:
        raise ValueError("taxonomy identity registry does not cover the approved definitions")
    values = tuple(TAXONOMY_PUBLIC_IDS.values())
    if len(values) != len(set(values)):
        raise ValueError("taxonomy public IDs must be unique")
    if any(uuid.UUID(value).version != 7 for value in values):
        raise ValueError("taxonomy public IDs must be UUIDv7")


validate_taxonomy_identity_registry()
