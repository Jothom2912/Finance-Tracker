"""Unit tests for BankingService.sync_transactions ensuring bank-
synced transactions are handed to transaction-service over HTTP
rather than written directly to MySQL.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from backend.banking.adapters.outbound.enable_banking_client import BankTransaction
from backend.banking.adapters.outbound.transaction_service_client import (
    BulkImportResult,
    TransactionServiceError,
)
from backend.banking.application.service import BankingService


class _StubAccount:
    def __init__(self, account_id: int = 1, user_id: int = 42, name: str = "Lønkonto"):
        self.idAccount = account_id
        self.User_idUser = user_id
        self.name = name


class _StubConnection:
    def __init__(self, account_id: int = 1, status: str = "active"):
        self.id = 10
        self.account_id = account_id
        self.bank_account_uid = "uid-abc"
        self.status = status
        self.last_synced_at = None


class _StubCategory:
    def __init__(self, id_: int = 7, name: str = "Mad"):
        self.idCategory = id_
        self.name = name


def _bank_tx(amount: float = -100.0, description: str = "Netto") -> BankTransaction:
    return BankTransaction(
        transaction_id="bank-1",
        amount=amount,
        currency="DKK",
        description=description,
        date=date(2026, 3, 15),
        raw={},
    )


def _make_db(connection, account, category) -> MagicMock:
    """Build a MagicMock DB session that returns the right object
    depending on which model is being queried."""
    from backend.models.mysql.account import Account as AccountModel
    from backend.models.mysql.bank_connection import BankConnection
    from backend.models.mysql.category import Category as CategoryModel

    def query_side_effect(model):
        q = MagicMock()
        if model is BankConnection:
            q.filter.return_value.first.return_value = connection
        elif model is AccountModel:
            q.filter.return_value.first.return_value = account
        elif model is CategoryModel:
            q.filter.return_value.first.return_value = category
        else:
            q.filter.return_value.first.return_value = None
        return q

    db = MagicMock()
    db.query.side_effect = query_side_effect
    return db


def _make_banking_service(
    bank_txns: list[BankTransaction],
    tx_client: MagicMock | None = None,
    connection: _StubConnection | None = None,
    account: _StubAccount | None = None,
    category: _StubCategory | None = None,
    categorization: MagicMock | None = None,
) -> tuple[BankingService, MagicMock, MagicMock]:
    connection = connection or _StubConnection()
    account = account or _StubAccount()
    category = category or _StubCategory()
    db = _make_db(connection, account, category)

    client = MagicMock()
    client.get_transactions.return_value = bank_txns

    tx_service = tx_client or MagicMock()
    if tx_client is None:
        tx_service.bulk_import.return_value = BulkImportResult(
            imported=len(bank_txns),
            duplicates_skipped=0,
            errors=0,
            imported_ids=list(range(1, len(bank_txns) + 1)),
        )

    service = BankingService(
        db=db,
        banking_client=client,
        categorization_service=categorization,
        transaction_service_client=tx_service,
    )
    return service, db, tx_service


class TestSyncTransactions:
    def test_routes_bank_transactions_to_transaction_service(self) -> None:
        txns = [_bank_tx(amount=-50.0), _bank_tx(amount=-25.5, description="Føtex")]
        service, db, tx_client = _make_banking_service(txns)

        result = service.sync_transactions(connection_id=10)

        assert result.total_fetched == 2
        assert result.new_imported == 2
        assert result.duplicates_skipped == 0
        assert result.errors == 0

        tx_client.bulk_import.assert_called_once()
        call_kwargs = tx_client.bulk_import.call_args
        assert call_kwargs.kwargs["user_id"] == 42
        items = list(call_kwargs.kwargs["items"])
        assert len(items) == 2
        assert items[0].account_id == 1
        assert items[0].transaction_type == "expense"
        assert items[0].amount == Decimal("50.00")

    def test_no_direct_mysql_writes(self) -> None:
        """Critical: BankingService must not write transactions to
        MySQL — those come back via the projection consumer.
        """
        service, db, _ = _make_banking_service([_bank_tx()])

        service.sync_transactions(connection_id=10)

        db.add.assert_not_called()

    def test_bulk_result_reflects_duplicates(self) -> None:
        tx_client = MagicMock()
        tx_client.bulk_import.return_value = BulkImportResult(
            imported=1,
            duplicates_skipped=2,
            errors=0,
            imported_ids=[5],
        )
        service, _, _ = _make_banking_service(
            [_bank_tx(), _bank_tx(), _bank_tx()],
            tx_client=tx_client,
        )

        result = service.sync_transactions(connection_id=10)

        assert result.new_imported == 1
        assert result.duplicates_skipped == 2
        assert result.total_fetched == 3

    def test_transaction_service_error_counted_as_errors(self) -> None:
        tx_client = MagicMock()
        tx_client.bulk_import.side_effect = TransactionServiceError("connection refused")
        service, _, _ = _make_banking_service(
            [_bank_tx(), _bank_tx()],
            tx_client=tx_client,
        )

        result = service.sync_transactions(connection_id=10)

        assert result.new_imported == 0
        assert result.errors == 2

    def test_raises_when_connection_missing(self) -> None:
        service, db, _ = _make_banking_service([])
        db.query.side_effect = lambda model: MagicMock(
            filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None))),
        )

        with pytest.raises(ValueError, match="not found"):
            service.sync_transactions(connection_id=99)

    def test_raises_when_connection_inactive(self) -> None:
        conn = _StubConnection(status="disconnected")
        service, _, _ = _make_banking_service([], connection=conn)

        with pytest.raises(ValueError, match="disconnected"):
            service.sync_transactions(connection_id=10)

    def test_categorization_drives_category_id(self) -> None:
        from backend.category.domain.value_objects import (
            CategorizationResult,
            CategorizationTier,
            Confidence,
        )

        categorization = MagicMock()
        categorization.categorize.return_value = MagicMock(
            result=CategorizationResult(
                category_id=7,
                subcategory_id=None,
                merchant_id=None,
                tier=CategorizationTier.RULE,
                confidence=Confidence.HIGH,
            ),
        )
        service, _, tx_client = _make_banking_service(
            [_bank_tx(description="Netto")],
            categorization=categorization,
        )

        service.sync_transactions(connection_id=10)

        items = list(tx_client.bulk_import.call_args.kwargs["items"])
        assert items[0].category_id == 7
        assert items[0].category_name == "Mad"

    def test_pipeline_metadata_reaches_http_client(self) -> None:
        """Rule-engine tier + confidence + subcategory_id must survive
        the hand-off to transaction-service so the projection can
        surface them as dashboard tier-badges.
        """
        from backend.category.domain.value_objects import (
            CategorizationResult,
            CategorizationTier,
            Confidence,
        )

        categorization = MagicMock()
        categorization.categorize.return_value = MagicMock(
            result=CategorizationResult(
                category_id=7,
                subcategory_id=42,
                merchant_id=None,
                tier=CategorizationTier.RULE,
                confidence=Confidence.HIGH,
            ),
        )
        service, _, tx_client = _make_banking_service(
            [_bank_tx(description="Netto")],
            categorization=categorization,
        )

        service.sync_transactions(connection_id=10)

        item = list(tx_client.bulk_import.call_args.kwargs["items"])[0]
        assert item.subcategory_id == 42
        assert item.categorization_tier == "rule"
        assert item.categorization_confidence == "high"

    def test_no_pipeline_metadata_when_categorizer_absent(self) -> None:
        """When categorization service isn't wired, the three fields
        stay None — we don't fabricate tier information.
        """
        service, _, tx_client = _make_banking_service(
            [_bank_tx()],
            categorization=None,
        )

        service.sync_transactions(connection_id=10)

        item = list(tx_client.bulk_import.call_args.kwargs["items"])[0]
        assert item.subcategory_id is None
        assert item.categorization_tier is None
        assert item.categorization_confidence is None
