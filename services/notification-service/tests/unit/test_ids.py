from __future__ import annotations

from app.domain.ids import uuid7


def test_version_and_variant_bits() -> None:
    u = uuid7(timestamp_ms=1_700_000_000_000)
    assert u.version == 7
    # RFC 4122/9562 variant: two most-significant bits of clock_seq_hi are 0b10.
    assert (u.int >> 62) & 0b11 == 0b10


def test_timestamp_is_encoded_in_high_48_bits() -> None:
    ts = 1_700_000_000_123
    u = uuid7(timestamp_ms=ts)
    assert (u.int >> 80) == ts


def test_is_time_ordered() -> None:
    earlier = uuid7(timestamp_ms=1_000)
    later = uuid7(timestamp_ms=2_000)
    assert earlier < later


def test_ids_are_unique_within_same_millisecond() -> None:
    ids = {uuid7(timestamp_ms=42) for _ in range(1000)}
    assert len(ids) == 1000
