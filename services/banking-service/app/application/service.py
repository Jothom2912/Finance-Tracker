from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from contracts.events.bank import (
    BankConnectionCreatedEvent,
    BankConnectionDisconnectedEvent,
    BankSyncCompletedEvent,
)

from app.application.ports.outbound import (
    IBankingApiClient,
    IAccountPort,
    ITransactionImporter,
    IUnitOfWork,
)
from app.config import settings
from app.domain.entities import BankConnection, SyncResult
from app.domain.exceptions import (
    BankAccountNotOwned,
    BankConnectionInactive,
    BankConnectionNotFound,
    PendingAuthorizationNotFound,
    ProjectionIntegrityError,
)

logger = logging.getLogger(__name__)


class BankingService:
    def __init__(
        self,
        uow: IUnitOfWork,
        account_port: IAccountPort,
        banking_client: IBankingApiClient,
        transaction_importer: ITransactionImporter,
    ) -> None:
        self._uow = uow
        self._account_port = account_port
        self._client = banking_client
        self._tx_importer = transaction_importer

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

    async def list_banks(self, country: str = "DK") -> list[dict[str, Any]]:
        return self._client.get_available_banks(country)

    async def start_connect(
        self,
        bank_name: str,
        country: str,
        account_id: int,
        user_id: int,
    ) -> dict[str, str]:
        await self._verify_account_access(account_id, user_id)
        result = self._client.start_authorization(bank_name=bank_name, country=country)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.PENDING_AUTH_TTL_MINUTES)
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

        session = self._client.create_session(auth_code)
        session_id = session["session_id"]
        accounts = session.get("accounts", [])

        created: list[dict[str, Any]] = []
        async with self._uow:
            for bank_account in accounts:
                uid = bank_account.get("uid", "")
                iban = bank_account.get("account_id", {}).get("iban", "")

                existing = await self._uow.connections.get_active_by_uid(uid, account_id)
                if existing is not None:
                    await self._uow.connections.update_status(existing.id, "active")
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
                created.append({
                    "id": connection_id,
                    "bank_account_uid": uid,
                    "iban": iban,
                    "status": status,
                })

            await self._uow.commit()

        logger.info(
            "Connected %d bank accounts (session=%s)", len(created), session_id,
        )
        return created

    async def list_connections(self, account_id: int) -> list[dict[str, Any]]:
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

    async def sync_transactions(
        self,
        connection_id: UUID,
        user_id: int,
        date_from: Optional[str] = None,
    ) -> SyncResult:
        async with self._uow:
            conn = await self._uow.connections.get_by_id(connection_id)
        if conn is None:
            raise BankConnectionNotFound(connection_id)
        if not conn.is_active:
            raise BankConnectionInactive(connection_id, conn.status)
        if conn.user_id != user_id:
            raise BankAccountNotOwned(conn.account_id)

        try:
            account_name = await self._resolve_account_name(conn.account_id)
        except BankAccountNotOwned:
            raise ProjectionIntegrityError(conn.account_id)

        bank_transactions, parse_skipped = self._client.get_transactions(
            account_uid=conn.bank_account_uid,
            date_from=date_from,
        )

        items = []
        errors = 0
        for bank_txn in bank_transactions:
            try:
                tx_type = "income" if bank_txn.amount >= 0 else "expense"
                items.append({
                    "account_id": conn.account_id,
                    "account_name": account_name,
                    "amount": str(abs(bank_txn.amount)),
                    "transaction_type": tx_type,
                    "date": bank_txn.date.isoformat(),
                    "description": bank_txn.description,
                })
            except Exception:
                logger.exception(
                    "Error preparing transaction %s for bulk import",
                    getattr(bank_txn, "transaction_id", "<unknown>"),
                )
                errors += 1

        try:
            remote = self._tx_importer.bulk_import(user_id=user_id, items=items)
        except Exception:
            logger.exception(
                "transaction-service rejected bulk import (connection=%s)",
                connection_id,
            )
            async with self._uow:
                await self._uow.connections.update_last_synced(connection_id, datetime.utcnow())
                await self._uow.commit()
            return SyncResult(
                total_fetched=len(bank_transactions),
                new_imported=0,
                duplicates_skipped=0,
                errors=len(bank_transactions) + errors,
                parse_skipped=parse_skipped,
            )

        result = SyncResult(
            total_fetched=len(bank_transactions),
            new_imported=remote.imported,
            duplicates_skipped=remote.duplicates_skipped,
            errors=errors + remote.errors,
            parse_skipped=parse_skipped,
        )

        async with self._uow:
            await self._uow.connections.update_last_synced(connection_id, datetime.utcnow())
            await self._uow.outbox.add(
                event=BankSyncCompletedEvent(
                    connection_id=str(connection_id),
                    account_id=conn.account_id,
                    user_id=user_id,
                    total_fetched=result.total_fetched,
                    new_imported=result.new_imported,
                    duplicates_skipped=result.duplicates_skipped,
                    errors=result.errors,
                    parse_skipped=result.parse_skipped,
                ),
                aggregate_type="bank_connection",
                aggregate_id=str(connection_id),
            )
            await self._uow.commit()

        logger.info(
            "Sync complete for connection %s: %d fetched, %d new, %d dupes, %d errors, %d parse-skipped",
            connection_id,
            result.total_fetched,
            result.new_imported,
            result.duplicates_skipped,
            result.errors,
            result.parse_skipped,
        )
        return result

    async def disconnect(self, connection_id: UUID) -> bool:
        async with self._uow:
            conn = await self._uow.connections.get_by_id(connection_id)
        if conn is None:
            return False
        try:
            self._client.delete_session(conn.session_id)
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
