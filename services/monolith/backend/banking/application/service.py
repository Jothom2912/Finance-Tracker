"""
Banking application service.

Handles bank connection flow and transaction sync.
Integrates with the categorization pipeline for auto-categorization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.banking.adapters.outbound.enable_banking_client import (
    BankTransaction,
    EnableBankingClient,
)
from backend.category.application.categorization_service import (
    CategorizationService,
    TransactionInput,
)
from backend.models.mysql.bank_connection import BankConnection
from backend.models.mysql.transaction import Transaction as TransactionModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Result of a transaction sync operation."""
    total_fetched: int
    new_imported: int
    duplicates_skipped: int
    errors: int


class BankingService:
    """
    Application service for bank connections and transaction sync.

    Orchestrates:
      1. Bank authorization (OAuth via Enable Banking)
      2. Transaction fetching from connected banks
      3. Auto-categorization via CategorizationService
      4. Deduplication and storage
    """

    def __init__(
        self,
        db: Session,
        banking_client: EnableBankingClient,
        categorization_service: Optional[CategorizationService] = None,
    ):
        self._db = db
        self._client = banking_client
        self._categorization = categorization_service

    # ──────────────────────────────────────────
    # Bank discovery
    # ──────────────────────────────────────────

    def list_banks(self, country: str = "DK") -> list[dict[str, Any]]:
        """List available banks for a country."""
        return self._client.get_available_banks(country)

    # ──────────────────────────────────────────
    # Authorization flow
    # ──────────────────────────────────────────

    def start_connect(
        self, bank_name: str, country: str = "DK"
    ) -> dict[str, str]:
        """Start bank connection. Returns URL to redirect user to."""
        return self._client.start_authorization(
            bank_name=bank_name, country=country
        )

    def complete_connect(
        self, auth_code: str, account_id: int
    ) -> list[dict[str, Any]]:
        """
        Complete bank connection after user authorization.

        Creates a BankConnection for each bank account found.
        Returns list of created connections.
        """
        session = self._client.create_session(auth_code)
        session_id = session["session_id"]
        accounts = session.get("accounts", [])

        created_connections = []
        for bank_account in accounts:
            uid = bank_account.get("uid", "")
            iban = bank_account.get("account_id", {}).get("iban", "")

            existing = (
                self._db.query(BankConnection)
                .filter(BankConnection.bank_account_uid == uid)
                .first()
            )
            if existing:
                existing.session_id = session_id
                existing.status = "active"
                self._db.flush()
                created_connections.append({
                    "id": existing.id,
                    "bank_account_uid": uid,
                    "iban": iban,
                    "status": "reconnected",
                })
                continue

            conn = BankConnection(
                account_id=account_id,
                session_id=session_id,
                bank_name=session.get("aspsp", {}).get("name", "Unknown"),
                bank_country=session.get("aspsp", {}).get("country", "DK"),
                bank_account_uid=uid,
                bank_account_iban=iban,
                status="active",
            )
            self._db.add(conn)
            self._db.flush()
            created_connections.append({
                "id": conn.id,
                "bank_account_uid": uid,
                "iban": iban,
                "status": "new",
            })

        self._db.commit()
        logger.info(
            "Connected %d bank accounts (session=%s)",
            len(created_connections), session_id,
        )
        return created_connections

    # ──────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────

    def list_connections(self, account_id: int) -> list[dict[str, Any]]:
        """List all bank connections for an account."""
        connections = (
            self._db.query(BankConnection)
            .filter(BankConnection.account_id == account_id)
            .all()
        )
        return [
            {
                "id": c.id,
                "bank_name": c.bank_name,
                "bank_country": c.bank_country,
                "iban": c.bank_account_iban,
                "status": c.status,
                "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in connections
        ]

    def disconnect(self, connection_id: int) -> bool:
        """Disconnect a bank connection."""
        conn = (
            self._db.query(BankConnection)
            .filter(BankConnection.id == connection_id)
            .first()
        )
        if not conn:
            return False

        try:
            self._client.delete_session(conn.session_id)
        except Exception:
            logger.warning("Failed to delete remote session %s", conn.session_id)

        conn.status = "disconnected"
        self._db.commit()
        return True

    # ──────────────────────────────────────────
    # Transaction sync
    # ──────────────────────────────────────────

    def sync_transactions(
        self,
        connection_id: int,
        date_from: Optional[str] = None,
    ) -> SyncResult:
        """
        Sync transactions from a connected bank account.

        Fetches transactions, deduplicates, auto-categorizes, and stores.
        """
        conn = (
            self._db.query(BankConnection)
            .filter(BankConnection.id == connection_id)
            .first()
        )
        if not conn:
            raise ValueError(f"Bank connection {connection_id} not found")
        if conn.status != "active":
            raise ValueError(f"Bank connection {connection_id} is {conn.status}")

        bank_transactions = self._client.get_transactions(
            account_uid=conn.bank_account_uid,
            date_from=date_from,
        )

        result = SyncResult(
            total_fetched=len(bank_transactions),
            new_imported=0,
            duplicates_skipped=0,
            errors=0,
        )

        for bank_txn in bank_transactions:
            try:
                if self._is_duplicate(bank_txn, conn.account_id):
                    result.duplicates_skipped += 1
                    continue

                self._import_transaction(bank_txn, conn.account_id)
                result.new_imported += 1

            except Exception:
                logger.exception(
                    "Error importing transaction %s", bank_txn.transaction_id
                )
                result.errors += 1

        conn.last_synced_at = datetime.now()
        self._db.commit()

        logger.info(
            "Sync complete for connection %d: %d fetched, %d new, %d dupes, %d errors",
            connection_id, result.total_fetched, result.new_imported,
            result.duplicates_skipped, result.errors,
        )
        return result

    def _is_duplicate(self, bank_txn: BankTransaction, account_id: int) -> bool:
        """Check if transaction already exists based on description + date + amount."""
        from sqlalchemy import and_

        existing = (
            self._db.query(TransactionModel)
            .filter(
                and_(
                    TransactionModel.Account_idAccount == account_id,
                    TransactionModel.description == bank_txn.description,
                    TransactionModel.amount == abs(bank_txn.amount),
                    TransactionModel.date == bank_txn.date,
                )
            )
            .first()
        )
        return existing is not None

    def _import_transaction(
        self, bank_txn: BankTransaction, account_id: int
    ) -> None:
        """Import a single bank transaction with auto-categorization."""
        tx_type = "income" if bank_txn.amount >= 0 else "expense"

        subcategory_id = None
        categorization_tier = None
        categorization_confidence = None
        category_id = None

        if self._categorization is not None:
            output = self._categorization.categorize(
                TransactionInput(
                    description=bank_txn.description,
                    amount=bank_txn.amount,
                )
            )
            category_id = output.result.category_id
            subcategory_id = output.result.subcategory_id
            categorization_tier = output.result.tier.value
            categorization_confidence = output.result.confidence.value

        if category_id is None:
            from backend.models.mysql.category import Category as CategoryModel
            fallback = (
                self._db.query(CategoryModel)
                .filter(CategoryModel.name == "Anden")
                .first()
            )
            category_id = fallback.idCategory if fallback else 1

        model = TransactionModel(
            amount=abs(bank_txn.amount),
            description=bank_txn.description,
            date=bank_txn.date,
            type=tx_type,
            Category_idCategory=category_id,
            Account_idAccount=account_id,
            created_at=datetime.now(),
            subcategory_id=subcategory_id,
            categorization_tier=categorization_tier,
            categorization_confidence=categorization_confidence,
        )
        self._db.add(model)
        self._db.flush()
