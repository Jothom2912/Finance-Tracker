"""Projection consumer that materialises account events into MySQL.

Listens on ``account.*`` and upserts rows in the monolith MySQL
``Account`` table so legacy contexts (analytics, budget, goals,
banking auth) can keep reading from their local database while
account-service owns the write path.

Follows the same pattern as TransactionSyncConsumer:
- UPSERT semantics (idempotent on re-delivery)
- Silently skips unknown event types with a warning
- Commits the MySQL session per event; re-raises to let BaseConsumer
  apply retry + DLQ
- saldo parsed as Decimal (never float) to preserve precision
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal, InvalidOperation

from backend.consumers.base import BaseConsumer
from backend.models.mysql.account import Account as AccountModel

logger = logging.getLogger(__name__)

_HANDLERS = {
    "account.created": "_sync_created",
    "account.updated": "_sync_updated",
}


class AccountSyncConsumer(BaseConsumer):
    """Materialise account events from account-service into
    monolith MySQL as a read model.
    """

    def __init__(
        self,
        rabbitmq_url: str,
        db_session_factory: object,
    ) -> None:
        super().__init__(
            rabbitmq_url=rabbitmq_url,
            queue_name="monolith.account_sync",
            routing_key="account.*",
            db_session_factory=db_session_factory,
        )
        self._session_factory = db_session_factory

    async def handle(self, event_data: dict[str, object]) -> None:
        event_type = str(event_data.get("event_type", ""))
        handler_name = _HANDLERS.get(event_type)
        if handler_name is None:
            logger.warning("Unknown account event type: %s — skipping", event_type)
            return

        handler = getattr(self, handler_name)
        await asyncio.to_thread(handler, event_data)

    def _sync_created(self, event_data: dict[str, object]) -> None:
        account_id = int(event_data["account_id"])
        user_id = int(event_data["user_id"])
        name = str(event_data.get("account_name") or event_data.get("name", ""))
        saldo = self._parse_saldo(event_data.get("saldo", "0"))
        budget_start_day = int(event_data.get("budget_start_day", 1))

        session = self._session_factory()
        try:
            existing = (
                session.query(AccountModel)
                .filter(AccountModel.idAccount == account_id)
                .first()
            )
            if existing is not None:
                existing.name = name
                existing.saldo = saldo
                existing.User_idUser = user_id
                existing.budget_start_day = budget_start_day
                session.commit()
                logger.info(
                    "Account %d already exists — updated (replay/upsert)",
                    account_id,
                )
                return

            model = AccountModel(
                idAccount=account_id,
                name=name,
                saldo=saldo,
                User_idUser=user_id,
                budget_start_day=budget_start_day,
            )
            session.add(model)
            session.commit()
            logger.info(
                "Synced new account %d for user %d (%s)",
                account_id,
                user_id,
                name,
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _sync_updated(self, event_data: dict[str, object]) -> None:
        account_id = int(event_data["account_id"])
        user_id = int(event_data["user_id"])
        name = str(event_data.get("name", ""))
        saldo = self._parse_saldo(event_data.get("saldo", "0"))
        budget_start_day = int(event_data.get("budget_start_day", 1))

        session = self._session_factory()
        try:
            existing = (
                session.query(AccountModel)
                .filter(AccountModel.idAccount == account_id)
                .first()
            )
            if existing is not None:
                existing.name = name
                existing.saldo = saldo
                existing.User_idUser = user_id
                existing.budget_start_day = budget_start_day
                session.commit()
                logger.info("Updated account %d (%s)", account_id, name)
            else:
                model = AccountModel(
                    idAccount=account_id,
                    name=name,
                    saldo=saldo,
                    User_idUser=user_id,
                    budget_start_day=budget_start_day,
                )
                session.add(model)
                session.commit()
                logger.info(
                    "Account %d not found for update — inserted (self-healing)",
                    account_id,
                )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _parse_saldo(value: object) -> Decimal:
        """Parse saldo as Decimal, never float. Preserves precision for MySQL DECIMAL column."""
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            logger.warning("Invalid saldo value '%s', defaulting to 0", value)
            return Decimal("0")
