from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID


def _as_utc(dt: datetime) -> datetime:
    """Normalise naive datetimes (stored as UTC wall-clock) to aware UTC."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


@dataclass
class BankConnection:
    account_id: int
    user_id: int
    session_id: str
    bank_name: str
    bank_country: str
    bank_account_uid: str
    id: Optional[UUID] = None
    bank_account_iban: Optional[str] = None
    status: str = "active"
    expires_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    sync_saga_id: Optional[str] = None
    sync_started_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    def is_sync_due(self, now: datetime, every_hours: int) -> bool:
        """True når forbindelsen er moden til scheduled sync (F1-05):
        aldrig synket, eller sidste sync ældre end ``every_hours``.
        ``now`` fra injiceret clock; ``last_synced_at`` kan være naiv
        (UTC wall-clock fra DB) — begge normaliseres."""
        if self.last_synced_at is None:
            return True
        return _as_utc(now) - _as_utc(self.last_synced_at) >= timedelta(hours=every_hours)

    def sync_claim_is_stale(self, now: datetime, ttl_seconds: int) -> bool:
        """True if the in-flight sync-claim is older than the TTL backstop.

        Used only as fallback when the claimed saga's status cannot be
        checked — a crashed/never-resolved saga must not block syncs forever.
        """
        if self.sync_started_at is None:
            return True
        age = _as_utc(now) - _as_utc(self.sync_started_at)
        return age.total_seconds() > ttl_seconds

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def is_expired_at(self, now: datetime) -> bool:
        """True if the bank consent has expired at the given instant.

        ``now`` comes from an injected clock (see app/domain/clock.py) —
        never call ``datetime.now()`` here. ``expires_at`` may be naive
        (UTC wall-clock from the DB) or aware; both are normalised.
        """
        if self.expires_at is None:
            return False
        return _as_utc(now) > _as_utc(self.expires_at)


@dataclass
class OutboxEntry:
    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload_json: str
    correlation_id: str | None
    status: str
    attempts: int
    next_attempt_at: datetime
    created_at: datetime
