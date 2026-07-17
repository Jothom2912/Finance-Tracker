from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from contracts.events.bank import (
    BankConnectionCreatedEvent,
    BankConnectionDisconnectedEvent,
)
from contracts.events.saga import BankSyncSagaStartEvent

from app.application.ports.outbound import (
    IAccountPort,
    IBankingApiClient,
    ISagaStatusPort,
    IUnitOfWork,
)
from app.config import settings
from app.domain.clock import Clock, utcnow
from app.domain.entities import BankConnection
from app.domain.exceptions import (
    BankAccountNotOwned,
    BankConnectionInactive,
    BankConnectionNotFound,
    BankConsentExpired,
    PendingAuthorizationNotFound,
    ProjectionIntegrityError,
)

logger = logging.getLogger(__name__)


# Statusser hvor sagaen med sikkerhed ikke længere arbejder — dens
# sync-claim kan overtages (P3-14).
_TERMINAL_SAGA_STATUSES = frozenset({"completed", "failed", "timed_out"})


class BankingService:
    def __init__(
        self,
        uow: IUnitOfWork,
        account_port: IAccountPort,
        banking_client: IBankingApiClient,
        clock: Clock = utcnow,
        saga_status_port: Optional[ISagaStatusPort] = None,
    ) -> None:
        self._uow = uow
        self._account_port = account_port
        self._client = banking_client
        self._clock = clock
        self._saga_status = saga_status_port

    async def _verify_account_access(self, account_id: int, user_id: int) -> None:
        async with self._uow:
            projection = await self._uow.accounts.get_projection(account_id)
        if projection is not None:
            owner_id, _ = projection
            if owner_id != user_id:
                raise BankAccountNotOwned(account_id)
            return
        owner_id = await self._account_port.get_owner_user_id(account_id)
        if owner_id != user_id:
            raise BankAccountNotOwned(account_id)

    async def _resolve_account_name(self, account_id: int) -> str:
        async with self._uow:
            projection = await self._uow.accounts.get_projection(account_id)
        if projection is not None:
            return projection[1]
        user_id, account_name = await self._account_port.get_account_info(account_id)
        async with self._uow:
            await self._uow.accounts.upsert(account_id, user_id, account_name)
            await self._uow.commit()
        return account_name

    @staticmethod
    def _parse_valid_until(session: dict[str, Any]) -> Optional[datetime]:
        """Extract consent expiry from an EB session payload.

        Enable Banking returns ISO-8601 in ``access.valid_until``.
        Returns None (never raises) on missing/malformed values — a
        connection without expiry is worse than one that fails to
        connect at all, so the caller logs a WARNING instead.
        """
        raw = (session.get("access") or {}).get("valid_until")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None

    async def list_banks(self, country: str = "DK") -> list[dict[str, Any]]:
        return await self._client.get_available_banks(country)

    async def start_connect(
        self,
        bank_name: str,
        country: str,
        account_id: int,
        user_id: int,
    ) -> dict[str, str]:
        await self._verify_account_access(account_id, user_id)
        result = await self._client.start_authorization(bank_name=bank_name, country=country)
        expires_at = self._clock() + timedelta(minutes=settings.PENDING_AUTH_TTL_MINUTES)
        async with self._uow:
            await self._uow.pending_auth.save(
                state=result["state"],
                account_id=account_id,
                user_id=user_id,
                expires_at=expires_at,
            )
            await self._uow.commit()
        return result

    async def complete_connect(
        self,
        auth_code: str,
        state: str,
    ) -> list[dict[str, Any]]:
        async with self._uow:
            await self._uow.pending_auth.cleanup_expired()
            auth = await self._uow.pending_auth.consume(state)
            if auth is None:
                raise PendingAuthorizationNotFound(state)
            account_id, user_id = auth
            await self._uow.commit()

        session = await self._client.create_session(auth_code)
        session_id = session["session_id"]
        accounts = session.get("accounts", [])
        consent_expires_at = self._parse_valid_until(session)
        if consent_expires_at is None:
            logger.warning(
                "EB session %s carried no parseable access.valid_until — "
                "expires_at left NULL, expiry gate will not trigger",
                session_id,
            )

        created: list[dict[str, Any]] = []
        async with self._uow:
            for bank_account in accounts:
                uid = bank_account.get("uid", "")
                iban = bank_account.get("account_id", {}).get("iban", "")

                existing = await self._uow.connections.get_active_by_uid(uid, account_id)
                if existing is not None:
                    await self._uow.connections.update_status(existing.id, "active")
                    # Reconsent produced a fresh EB session: refresh the
                    # stored session_id and consent expiry, otherwise the
                    # expiry gate would keep rejecting a renewed consent.
                    await self._uow.connections.update_consent(
                        existing.id,
                        session_id,
                        consent_expires_at,
                    )
                    connection_id = str(existing.id)
                    status = "reconnected"
                    bank_name = existing.bank_name
                else:
                    conn = BankConnection(
                        id=uuid4(),
                        account_id=account_id,
                        user_id=user_id,
                        session_id=session_id,
                        bank_name=session.get("aspsp", {}).get("name", "Unknown"),
                        bank_country=session.get("aspsp", {}).get("country", "DK"),
                        bank_account_uid=uid,
                        bank_account_iban=iban,
                        status="active",
                        expires_at=consent_expires_at,
                    )
                    await self._uow.connections.save(conn)
                    connection_id = str(conn.id)
                    status = "new"
                    bank_name = conn.bank_name

                await self._uow.outbox.add(
                    event=BankConnectionCreatedEvent(
                        connection_id=connection_id,
                        account_id=account_id,
                        user_id=user_id,
                        bank_name=bank_name,
                        iban=iban or None,
                        status=status,
                    ),
                    aggregate_type="bank_connection",
                    aggregate_id=connection_id,
                )
                created.append(
                    {
                        "id": connection_id,
                        "bank_account_uid": uid,
                        "iban": iban,
                        "status": status,
                    }
                )

            await self._uow.commit()

        logger.info(
            "Connected %d bank accounts (session=%s)",
            len(created),
            session_id,
        )
        return created

    async def list_connections(self, account_id: int, user_id: int) -> list[dict[str, Any]]:
        await self._verify_account_access(account_id, user_id)
        async with self._uow:
            connections = await self._uow.connections.list_by_account(account_id)
        return [
            {
                "id": str(c.id),
                "bank_name": c.bank_name,
                "bank_country": c.bank_country,
                "iban": c.bank_account_iban,
                "status": c.status,
                "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in connections
        ]

    async def start_sync_saga(
        self,
        connection_id: UUID,
        user_id: int,
        date_from: Optional[str] = None,
        bearer_token: Optional[str] = None,
    ) -> tuple[str, bool]:
        """Start an async bank-sync saga — at most one in-flight per connection (P3-14).

        Returns ``(saga_id, already_running)``. The atomic claim on
        ``bank_connections`` decides om vi starter en ny saga eller afleverer
        den kørende. ``bearer_token`` (kaldens eget JWT) bruges til status-
        opslag ved konflikt: terminal saga → claim steales; ukendt status →
        fail ACTIVE, så saga-service-nedetid aldrig giver duplikat-sagas
        (TTL'en i ``try_claim_sync`` er backstop mod claims der aldrig løses).
        """
        async with self._uow:
            conn = await self._uow.connections.get_by_id(connection_id)
        if conn is None:
            raise BankConnectionNotFound(connection_id)
        if not conn.is_active:
            raise BankConnectionInactive(connection_id, conn.status)
        if conn.user_id != user_id:
            raise BankAccountNotOwned(conn.account_id)
        if conn.is_expired_at(self._clock()):
            raise BankConsentExpired(connection_id, conn.expires_at)

        try:
            account_name = await self._resolve_account_name(conn.account_id)
        except BankAccountNotOwned:
            raise ProjectionIntegrityError(conn.account_id)

        saga_id = str(uuid4())
        now = self._clock()

        # Claim + start-event i SAMME transaktion: vinder claimet, findes
        # eventet; taber det, persisteres intet.
        async with self._uow:
            if await self._uow.connections.try_claim_sync(
                connection_id, saga_id, now, settings.SYNC_CLAIM_TTL_SECONDS
            ):
                await self._add_sync_start_event(saga_id, conn, connection_id, user_id, account_name, date_from)
                await self._uow.commit()
                logger.info(
                    "Bank sync saga started: saga_id=%s connection=%s user=%s",
                    saga_id,
                    connection_id,
                    user_id,
                )
                return saga_id, False
            await self._uow.rollback()

        # Konflikt: der er et in-flight claim.
        existing_id = await self._current_claim(connection_id)
        if existing_id is None:
            # Claimet forsvandt mellem forsøgene (sync afsluttet netop nu) —
            # prøv claim én gang til; taber vi igen, afleverer vi vinderens id.
            async with self._uow:
                if await self._uow.connections.try_claim_sync(
                    connection_id, saga_id, now, settings.SYNC_CLAIM_TTL_SECONDS
                ):
                    await self._add_sync_start_event(saga_id, conn, connection_id, user_id, account_name, date_from)
                    await self._uow.commit()
                    return saga_id, False
                await self._uow.rollback()
            return (await self._current_claim(connection_id)) or saga_id, True

        status = None
        if self._saga_status is not None:
            status = await self._saga_status.get_status(existing_id, bearer_token)

        if status in _TERMINAL_SAGA_STATUSES:
            async with self._uow:
                if await self._uow.connections.steal_sync_claim(connection_id, existing_id, saga_id, now):
                    await self._add_sync_start_event(saga_id, conn, connection_id, user_id, account_name, date_from)
                    await self._uow.commit()
                    logger.info(
                        "Bank sync saga started (stole %s claim %s): saga_id=%s connection=%s",
                        status,
                        existing_id,
                        saga_id,
                        connection_id,
                    )
                    return saga_id, False
                await self._uow.rollback()
            # Tabt steal-kapløb — aflever vinderens claim.
            return (await self._current_claim(connection_id)) or existing_id, True

        logger.info(
            "Bank sync already running: saga_id=%s (status=%s) connection=%s",
            existing_id,
            status or "unknown",
            connection_id,
        )
        return existing_id, True

    async def _current_claim(self, connection_id: UUID) -> Optional[str]:
        async with self._uow:
            conn = await self._uow.connections.get_by_id(connection_id)
        return conn.sync_saga_id if conn else None

    async def _add_sync_start_event(
        self,
        saga_id: str,
        conn: BankConnection,
        connection_id: UUID,
        user_id: int,
        account_name: str,
        date_from: Optional[str],
    ) -> None:
        await self._uow.outbox.add(
            event=BankSyncSagaStartEvent(
                correlation_id=saga_id,
                connection_id=str(connection_id),
                user_id=user_id,
                account_id=conn.account_id,
                account_name=account_name,
                bank_account_uid=conn.bank_account_uid,
                date_from=date_from,
            ),
            aggregate_type="bank_connection",
            aggregate_id=str(connection_id),
        )

    async def disconnect(self, connection_id: UUID, user_id: int) -> bool:
        async with self._uow:
            conn = await self._uow.connections.get_by_id(connection_id)
        if conn is None:
            return False
        if conn.user_id != user_id:
            raise BankAccountNotOwned(conn.account_id)
        try:
            await self._client.delete_session(conn.session_id)
        except Exception:
            logger.warning("Failed to delete remote session %s", conn.session_id)

        async with self._uow:
            await self._uow.connections.update_status(connection_id, "disconnected")
            await self._uow.outbox.add(
                event=BankConnectionDisconnectedEvent(
                    connection_id=str(connection_id),
                    account_id=conn.account_id,
                    user_id=conn.user_id,
                    bank_name=conn.bank_name,
                    iban=conn.bank_account_iban,
                ),
                aggregate_type="bank_connection",
                aggregate_id=str(connection_id),
            )
            await self._uow.commit()
        return True
