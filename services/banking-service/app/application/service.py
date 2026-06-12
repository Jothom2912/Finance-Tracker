from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID, uuid4

from app.application.ports.outbound import (
    IAccountProjection,
    IBankConnectionRepository,
    IBankingApiClient,
    IPendingAuthorizationRepository,
    ITransactionImporter,
)
from app.config import settings
from app.domain.entities import BankConnection, SyncResult
from app.domain.exceptions import (
    BankConnectionInactive,
    BankConnectionNotFound,
    PendingAuthorizationNotFound,
)

logger = logging.getLogger(__name__)


class BankingService:
    def __init__(
        self,
        bank_connection_repo: IBankConnectionRepository,
        pending_auth_repo: IPendingAuthorizationRepository,
        account_projection: IAccountProjection,
        banking_client: IBankingApiClient,
        transaction_importer: ITransactionImporter,
    ) -> None:
        self._connections = bank_connection_repo
        self._pending_auth = pending_auth_repo
        self._accounts = account_projection
        self._client = banking_client
        self._tx_importer = transaction_importer

    async def list_banks(self, country: str = "DK") -> list[dict[str, Any]]:
        return self._client.get_available_banks(country)

    async def start_connect(
        self,
        bank_name: str,
        country: str,
        account_id: int,
        user_id: int,
    ) -> dict[str, str]:
        result = self._client.start_authorization(bank_name=bank_name, country=country)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.PENDING_AUTH_TTL_MINUTES)
        await self._pending_auth.save(
            state=result["state"],
            account_id=account_id,
            user_id=user_id,
            expires_at=expires_at,
        )
        return result

    async def complete_connect(
        self,
        auth_code: str,
        state: str,
    ) -> list[dict[str, Any]]:
        await self._pending_auth.cleanup_expired()

        auth = await self._pending_auth.consume(state)
        if auth is None:
            raise PendingAuthorizationNotFound(state)
        account_id, user_id = auth

        session = self._client.create_session(auth_code)
        session_id = session["session_id"]
        accounts = session.get("accounts", [])

        created: list[dict[str, Any]] = []
        for bank_account in accounts:
            uid = bank_account.get("uid", "")
            iban = bank_account.get("account_id", {}).get("iban", "")

            existing = await self._connections.get_active_by_uid(uid, account_id)
            if existing is not None:
                await self._connections.update_status(existing.id, "active")
                created.append({
                    "id": str(existing.id),
                    "bank_account_uid": uid,
                    "iban": iban,
                    "status": "reconnected",
                })
                continue

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
            await self._connections.save(conn)
            created.append({
                "id": str(conn.id),
                "bank_account_uid": uid,
                "iban": iban,
                "status": "new",
            })

        await self._connections.commit()
        logger.info(
            "Connected %d bank accounts (session=%s)", len(created), session_id,
        )
        return created

    async def list_connections(self, account_id: int) -> list[dict[str, Any]]:
        connections = await self._connections.list_by_account(account_id)
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
        conn = await self._connections.get_by_id(connection_id)
        if conn is None:
            raise BankConnectionNotFound(connection_id)
        if not conn.is_active:
            raise BankConnectionInactive(connection_id, conn.status)

        account_name = await self._accounts.get_account_name(conn.account_id)
        if account_name is None:
            account_name = "Bank Account"

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
            await self._connections.update_last_synced(connection_id, datetime.utcnow())
            return SyncResult(
                total_fetched=len(bank_transactions),
                new_imported=0,
                duplicates_skipped=0,
                errors=len(bank_transactions) + errors,
                parse_skipped=parse_skipped,
            )

        await self._connections.update_last_synced(connection_id, datetime.utcnow())

        result = SyncResult(
            total_fetched=len(bank_transactions),
            new_imported=remote.imported,
            duplicates_skipped=remote.duplicates_skipped,
            errors=errors + remote.errors,
            parse_skipped=parse_skipped,
        )
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
        conn = await self._connections.get_by_id(connection_id)
        if conn is None:
            return False
        try:
            self._client.delete_session(conn.session_id)
        except Exception:
            logger.warning("Failed to delete remote session %s", conn.session_id)
        await self._connections.update_status(connection_id, "disconnected")
        return True
