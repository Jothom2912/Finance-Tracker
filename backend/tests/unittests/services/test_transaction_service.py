"""
Unit tests for TransactionService business logic.

Tests use Mock objects for all repositories, so no database is needed.
Each test verifies a specific piece of business logic in the service layer.

Updated for hexagonal architecture (backend.transaction.*).
"""

import pytest
from unittest.mock import Mock
from datetime import date, datetime

from backend.transaction.application.service import TransactionService
from backend.transaction.application.ports.outbound import (
    ITransactionRepository,
    ICategoryPort,
    IPlannedTransactionRepository,
)
from backend.transaction.domain.entities import (
    CategoryInfo,
    PlannedTransaction,
    Transaction,
)
from backend.transaction.domain.exceptions import (
    AccountRequired,
    CategoryNotFound,
    PlannedTransactionRepositoryNotConfigured,
)
from backend.shared.schemas.transaction import TransactionCreate, TransactionType
from backend.shared.schemas.planned_transactions import (
    PlannedTransactionsCreate,
    PlannedTransactionsBase,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_transaction_repo():
    return Mock(spec=ITransactionRepository)


@pytest.fixture
def mock_category_repo():
    return Mock(spec=ICategoryPort)


@pytest.fixture
def mock_planned_repo():
    return Mock(spec=IPlannedTransactionRepository)


@pytest.fixture
def service(mock_transaction_repo, mock_category_repo, mock_planned_repo):
    """TransactionService with all repos injected."""
    return TransactionService(
        transaction_repo=mock_transaction_repo,
        category_port=mock_category_repo,
        planned_transaction_repo=mock_planned_repo,
    )


@pytest.fixture
def service_without_planned(mock_transaction_repo, mock_category_repo):
    """TransactionService without planned transaction repo."""
    return TransactionService(
        transaction_repo=mock_transaction_repo,
        category_port=mock_category_repo,
    )


def _make_transaction_create(**overrides):
    """Helper to build a valid TransactionCreate with sensible defaults."""
    defaults = {
        "amount": -500.0,
        "type": TransactionType.expense,
        "description": "Netto",
        "Category_idCategory": 1,
        "Account_idAccount": 1,
        "date": date.today(),
    }
    defaults.update(overrides)
    return TransactionCreate(**defaults)


def _make_transaction_entity(
    tx_id: int = 1,
    amount: float = -500.0,
    tx_type: str = "expense",
    tx_date: date | None = None,
    category_id: int = 1,
    account_id: int = 1,
    description: str = "Netto",
) -> Transaction:
    return Transaction(
        id=tx_id,
        amount=amount,
        description=description,
        date=tx_date or date.today(),
        type=tx_type,
        category_id=category_id,
        account_id=account_id,
        created_at=datetime.now(),
    )


def _make_category_info(
    category_id: int = 1,
    name: str = "Mad",
    category_type: str = "expense",
) -> CategoryInfo:
    return CategoryInfo(id=category_id, name=name, type=category_type)


def _make_planned_entity(
    pt_id: int = 1, name: str = "Husleje", amount: float = -8000.0
) -> PlannedTransaction:
    return PlannedTransaction(id=pt_id, name=name, amount=amount)


# ============================================================================
# list_transactions
# ============================================================================


class TestListTransactions:
    """Tests for list_transactions query method."""

    def test_delegates_to_repository(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = []

        # Act
        service.list_transactions(account_id=1)

        # Assert
        mock_transaction_repo.get_all.assert_called_once_with(
            start_date=None,
            end_date=None,
            category_id=None,
            account_id=1,
            limit=100,
            offset=0,
        )

    def test_returns_repository_result(self, service, mock_transaction_repo):
        # Arrange
        expected = [_make_transaction_entity(tx_id=1, amount=-500.0)]
        mock_transaction_repo.get_all.return_value = expected

        # Act
        result = service.list_transactions(account_id=1)

        # Assert
        assert len(result) == 1
        assert result[0].idTransaction == 1
        assert result[0].amount == -500.0

    def test_returns_empty_list_when_no_data(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = []

        # Act
        result = service.list_transactions(account_id=1)

        # Assert
        assert result == []

    def test_raises_when_account_id_is_none(self, service):
        # Act & Assert
        with pytest.raises(AccountRequired):
            service.list_transactions(account_id=None)

    def test_passes_filter_parameters(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = []
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)

        # Act
        service.list_transactions(
            account_id=1,
            start_date=start,
            end_date=end,
            category_id=5,
            skip=10,
            limit=50,
        )

        # Assert
        mock_transaction_repo.get_all.assert_called_once_with(
            start_date=start,
            end_date=end,
            category_id=5,
            account_id=1,
            limit=50,
            offset=10,
        )

    def test_filters_by_type(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = [
            _make_transaction_entity(tx_id=1, tx_type="expense"),
            _make_transaction_entity(tx_id=2, tx_type="income", amount=500.0),
            _make_transaction_entity(tx_id=3, tx_type="expense", amount=-300.0),
        ]

        # Act
        result = service.list_transactions(account_id=1, tx_type="expense")

        # Assert
        assert len(result) == 2
        assert all(t.type == "expense" for t in result)

    def test_type_filter_is_case_insensitive(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = [
            _make_transaction_entity(tx_id=1, tx_type="expense"),
        ]

        # Act
        result = service.list_transactions(account_id=1, tx_type="EXPENSE")

        # Assert
        assert len(result) == 1

    def test_filters_by_month(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = [
            _make_transaction_entity(tx_id=1, tx_date=date(2024, 1, 15)),
            _make_transaction_entity(tx_id=2, tx_date=date(2024, 2, 15)),
            _make_transaction_entity(tx_id=3, tx_date=date(2024, 1, 28)),
        ]

        # Act
        result = service.list_transactions(account_id=1, month="01")

        # Assert
        assert len(result) == 2

    def test_filters_by_year(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = [
            _make_transaction_entity(tx_id=1, tx_date=date(2024, 6, 15)),
            _make_transaction_entity(tx_id=2, tx_date=date(2023, 6, 15)),
        ]

        # Act
        result = service.list_transactions(account_id=1, year="2024")

        # Assert
        assert len(result) == 1
        assert result[0].idTransaction == 1

    def test_filters_by_month_and_year_combined(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_all.return_value = [
            _make_transaction_entity(tx_id=1, tx_date=date(2024, 3, 10)),
            _make_transaction_entity(tx_id=2, tx_date=date(2024, 4, 10)),
            _make_transaction_entity(tx_id=3, tx_date=date(2023, 3, 10)),
        ]

        # Act
        result = service.list_transactions(account_id=1, month="03", year="2024")

        # Assert
        assert len(result) == 1
        assert result[0].idTransaction == 1


# ============================================================================
# get_transaction
# ============================================================================


class TestGetTransaction:
    """Tests for get_transaction query method."""

    def test_returns_transaction_when_found(self, service, mock_transaction_repo):
        # Arrange
        expected = _make_transaction_entity(tx_id=1, amount=-500.0, description="Netto")
        mock_transaction_repo.get_by_id.return_value = expected

        # Act
        result = service.get_transaction(transaction_id=1)

        # Assert
        assert result.idTransaction == 1
        assert result.amount == -500.0
        assert result.description == "Netto"

    def test_returns_none_when_not_found(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_by_id.return_value = None

        # Act
        result = service.get_transaction(transaction_id=999)

        # Assert
        assert result is None

    def test_delegates_to_repository(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.get_by_id.return_value = None

        # Act
        service.get_transaction(transaction_id=42)

        # Assert
        mock_transaction_repo.get_by_id.assert_called_once_with(42)


# ============================================================================
# create_transaction
# ============================================================================


class TestCreateTransaction:
    """Tests for create_transaction business logic."""

    def test_creates_transaction_successfully(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_by_id.return_value = _make_category_info(1, "Mad")
        mock_transaction_repo.create.return_value = _make_transaction_entity(
            tx_id=1, amount=-500.0, description="Netto"
        )
        transaction = _make_transaction_create()

        # Act
        result = service.create_transaction(transaction)

        # Assert
        assert result.idTransaction == 1
        mock_transaction_repo.create.assert_called_once()

    def test_raises_when_category_not_found(self, service, mock_category_repo):
        # Arrange
        mock_category_repo.get_by_id.return_value = None
        transaction = _make_transaction_create(Category_idCategory=999)

        # Act & Assert
        with pytest.raises(CategoryNotFound):
            service.create_transaction(transaction)

    def test_raises_when_account_id_missing(self, service, mock_category_repo):
        # Arrange
        mock_category_repo.get_by_id.return_value = _make_category_info(1, "Mad")
        transaction = _make_transaction_create(Account_idAccount=None)

        # Act & Assert
        with pytest.raises(AccountRequired):
            service.create_transaction(transaction)

    def test_sets_date_to_today_when_not_provided(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_by_id.return_value = _make_category_info(1, "Mad")
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)
        # TransactionCreate defaults date to today via schema, so we verify
        # the data passed to repo includes today's date
        transaction = _make_transaction_create()

        # Act
        service.create_transaction(transaction)

        # Assert
        call_data = mock_transaction_repo.create.call_args[0][0]
        assert call_data.date == date.today()

    def test_sets_created_at_timestamp(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_by_id.return_value = _make_category_info(1, "Mad")
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)
        transaction = _make_transaction_create()

        # Act
        service.create_transaction(transaction)

        # Assert
        call_data = mock_transaction_repo.create.call_args[0][0]
        assert call_data.created_at is not None
        assert isinstance(call_data.created_at, datetime)

    def test_converts_type_enum_to_string(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_by_id.return_value = _make_category_info(1, "Mad")
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)
        transaction = _make_transaction_create(type=TransactionType.expense)

        # Act
        service.create_transaction(transaction)

        # Assert
        call_data = mock_transaction_repo.create.call_args[0][0]
        assert call_data.type == "expense"

    def test_validates_category_before_creating(
        self, service, mock_category_repo, mock_transaction_repo
    ):
        # Arrange
        mock_category_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(CategoryNotFound):
            service.create_transaction(_make_transaction_create())

        # Repository create should NOT have been called
        mock_transaction_repo.create.assert_not_called()


# ============================================================================
# update_transaction
# ============================================================================


class TestUpdateTransaction:
    """Tests for update_transaction business logic."""

    def test_returns_none_when_transaction_not_found(
        self, service, mock_transaction_repo
    ):
        # Arrange
        mock_transaction_repo.get_by_id.return_value = None

        # Act
        result = service.update_transaction(
            transaction_id=999,
            dto=_make_transaction_create(),
        )

        # Assert
        assert result is None

    def test_updates_successfully(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        existing = _make_transaction_entity(tx_id=1, category_id=1, amount=-500.0)
        mock_transaction_repo.get_by_id.return_value = existing
        mock_transaction_repo.update.return_value = _make_transaction_entity(
            tx_id=1, amount=-600.0
        )
        update_data = _make_transaction_create(amount=-600.0)

        # Act
        result = service.update_transaction(
            transaction_id=1, dto=update_data
        )

        # Assert
        assert result.amount == -600.0
        mock_transaction_repo.update.assert_called_once()

    def test_validates_new_category_when_changed(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        existing = _make_transaction_entity(tx_id=1, category_id=1)
        mock_transaction_repo.get_by_id.return_value = existing
        mock_category_repo.get_by_id.return_value = None  # New category doesn't exist
        update_data = _make_transaction_create(Category_idCategory=999)

        # Act & Assert
        with pytest.raises(CategoryNotFound):
            service.update_transaction(transaction_id=1, dto=update_data)

    def test_skips_category_validation_when_unchanged(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        existing = _make_transaction_entity(tx_id=1, category_id=1)
        mock_transaction_repo.get_by_id.return_value = existing
        mock_transaction_repo.update.return_value = _make_transaction_entity(tx_id=1)
        update_data = _make_transaction_create(Category_idCategory=1)

        # Act
        service.update_transaction(transaction_id=1, dto=update_data)

        # Assert - category_repo.get_by_id should NOT have been called
        mock_category_repo.get_by_id.assert_not_called()

    def test_converts_type_enum_to_string_in_update(
        self, service, mock_transaction_repo
    ):
        # Arrange
        existing = _make_transaction_entity(tx_id=1, category_id=1)
        mock_transaction_repo.get_by_id.return_value = existing
        mock_transaction_repo.update.return_value = _make_transaction_entity(tx_id=1)
        update_data = _make_transaction_create(type=TransactionType.income, amount=100.0)

        # Act
        service.update_transaction(transaction_id=1, dto=update_data)

        # Assert
        call_args = mock_transaction_repo.update.call_args
        update_entity = call_args[0][0]
        assert update_entity.type == "income"


# ============================================================================
# delete_transaction
# ============================================================================


class TestDeleteTransaction:
    """Tests for delete_transaction."""

    def test_delegates_to_repository(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.delete.return_value = True

        # Act
        service.delete_transaction(transaction_id=1)

        # Assert
        mock_transaction_repo.delete.assert_called_once_with(1)

    def test_returns_true_on_success(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.delete.return_value = True

        # Act
        result = service.delete_transaction(transaction_id=1)

        # Assert
        assert result is True

    def test_returns_false_when_not_found(self, service, mock_transaction_repo):
        # Arrange
        mock_transaction_repo.delete.return_value = False

        # Act
        result = service.delete_transaction(transaction_id=999)

        # Assert
        assert result is False


# ============================================================================
# Planned Transactions
# ============================================================================


class TestPlannedTransactions:
    """Tests for planned transaction methods on TransactionService."""

    def test_list_planned_transactions_delegates(self, service, mock_planned_repo):
        # Arrange
        mock_planned_repo.get_all.return_value = []

        # Act
        service.list_planned_transactions()

        # Assert
        mock_planned_repo.get_all.assert_called_once_with(skip=0, limit=100)

    def test_list_planned_transactions_with_pagination(self, service, mock_planned_repo):
        # Arrange
        mock_planned_repo.get_all.return_value = []

        # Act
        service.list_planned_transactions(skip=10, limit=25)

        # Assert
        mock_planned_repo.get_all.assert_called_once_with(skip=10, limit=25)

    def test_get_planned_transaction_returns_result(
        self, service, mock_planned_repo
    ):
        # Arrange
        expected = _make_planned_entity(pt_id=1, name="Husleje", amount=-8000.0)
        mock_planned_repo.get_by_id.return_value = expected

        # Act
        result = service.get_planned_transaction(pt_id=1)

        # Assert
        assert result.idPlannedTransactions == 1
        assert result.name == "Husleje"

    def test_get_planned_transaction_returns_none(
        self, service, mock_planned_repo
    ):
        # Arrange
        mock_planned_repo.get_by_id.return_value = None

        # Act
        result = service.get_planned_transaction(pt_id=999)

        # Assert
        assert result is None

    def test_create_planned_transaction_delegates(self, service, mock_planned_repo):
        # Arrange
        mock_planned_repo.create.return_value = _make_planned_entity(
            pt_id=1, name="Husleje"
        )
        pt_data = PlannedTransactionsCreate(
            name="Husleje",
            amount=-8000.0,
            planned_date=date.today(),
            repeat_interval="monthly",
        )

        # Act
        result = service.create_planned_transaction(pt_data)

        # Assert
        assert result.name == "Husleje"
        mock_planned_repo.create.assert_called_once()

    def test_update_planned_transaction_delegates(self, service, mock_planned_repo):
        # Arrange
        mock_planned_repo.get_by_id.return_value = _make_planned_entity(
            pt_id=1, name="Husleje"
        )
        mock_planned_repo.update.return_value = _make_planned_entity(
            pt_id=1, name="Husleje Ny", amount=-9000.0
        )
        pt_data = PlannedTransactionsBase(name="Husleje Ny", amount=-9000.0)

        # Act
        result = service.update_planned_transaction(pt_id=1, dto=pt_data)

        # Assert
        assert result.name == "Husleje Ny"
        mock_planned_repo.update.assert_called_once()

    def test_update_returns_none_when_not_found(self, service, mock_planned_repo):
        # Arrange
        mock_planned_repo.update.return_value = None
        pt_data = PlannedTransactionsBase(name="Test", amount=100.0)

        # Act
        result = service.update_planned_transaction(pt_id=999, dto=pt_data)

        # Assert
        assert result is None


# ============================================================================
# Planned Transactions - repo not configured
# ============================================================================


class TestPlannedTransactionsNotConfigured:
    """Tests that planned transaction methods raise when repo is not injected."""

    def test_list_raises_without_repo(self, service_without_planned):
        with pytest.raises(PlannedTransactionRepositoryNotConfigured):
            service_without_planned.list_planned_transactions()

    def test_get_raises_without_repo(self, service_without_planned):
        with pytest.raises(PlannedTransactionRepositoryNotConfigured):
            service_without_planned.get_planned_transaction(pt_id=1)

    def test_create_raises_without_repo(self, service_without_planned):
        pt_data = PlannedTransactionsCreate(name="Test", amount=100.0)
        with pytest.raises(PlannedTransactionRepositoryNotConfigured):
            service_without_planned.create_planned_transaction(pt_data)

    def test_update_raises_without_repo(self, service_without_planned):
        pt_data = PlannedTransactionsBase(name="Test", amount=100.0)
        with pytest.raises(PlannedTransactionRepositoryNotConfigured):
            service_without_planned.update_planned_transaction(pt_id=1, dto=pt_data)


# ============================================================================
# CSV Import
# ============================================================================


class TestImportFromCsv:
    """Tests for CSV import business logic."""

    def _make_csv(self, rows: str) -> bytes:
        """Helper to build CSV bytes with standard header."""
        header = "Bogføringsdato;Beløb;Modtager;Afsender;Navn;Beskrivelse"
        return f"{header}\n{rows}".encode("utf-8")

    def test_imports_valid_csv(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_all.return_value = [
            _make_category_info(1, "Anden"),
        ]
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)

        csv_data = self._make_csv("2024/01/15;-150,50;Netto;;;Netto køb")

        # Act
        result = service.import_from_csv(csv_data, account_id=1)

        # Assert
        assert len(result) == 1
        mock_transaction_repo.create.assert_called_once()

    def test_imports_multiple_rows(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_all.return_value = [
            _make_category_info(1, "Anden"),
        ]
        mock_transaction_repo.create.side_effect = [
            _make_transaction_entity(tx_id=1),
            _make_transaction_entity(tx_id=2),
        ]

        csv_data = self._make_csv(
            "2024/01/15;-150,50;Netto;;;Netto køb\n"
            "2024/01/16;-75,00;DSB;;;DSB billet"
        )

        # Act
        result = service.import_from_csv(csv_data, account_id=1)

        # Assert
        assert len(result) == 2

    def test_creates_anden_category_if_missing(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_all.return_value = []  # No categories exist
        mock_category_repo.create.return_value = _make_category_info(99, "Anden")
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)

        csv_data = self._make_csv("2024/01/15;-150,50;Netto;;;Netto køb")

        # Act
        service.import_from_csv(csv_data, account_id=1)

        # Assert
        mock_category_repo.create.assert_called_once()
        create_kwargs = mock_category_repo.create.call_args.kwargs
        assert create_kwargs["name"] == "Anden"

    def test_raises_on_empty_csv_after_parsing(
        self, service, mock_category_repo
    ):
        # Arrange - CSV with header but invalid dates that result in empty df
        csv_data = self._make_csv("not-a-date;-150,50;Netto;;;Netto køb")

        # Act & Assert
        with pytest.raises(ValueError, match="Ingen gyldige transaktioner"):
            service.import_from_csv(csv_data, account_id=1)

    def test_raises_on_missing_date_column(self, service):
        # Arrange
        csv_data = b"Navn;Beloeb\nTest;100"

        # Act & Assert
        with pytest.raises(ValueError, match="CSV mangler"):
            service.import_from_csv(csv_data, account_id=1)

    def test_sets_account_id_on_imported_transactions(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_all.return_value = [
            _make_category_info(1, "Anden"),
        ]
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)

        csv_data = self._make_csv("2024/01/15;-150,50;Netto;;;Netto køb")

        # Act
        service.import_from_csv(csv_data, account_id=42)

        # Assert
        call_data = mock_transaction_repo.create.call_args[0][0]
        assert call_data.account_id == 42

    def test_negative_amount_is_categorized_as_expense(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_all.return_value = [
            _make_category_info(1, "Anden"),
        ]
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)

        csv_data = self._make_csv("2024/01/15;-150,50;Netto;;;Netto køb")

        # Act
        service.import_from_csv(csv_data, account_id=1)

        # Assert
        call_data = mock_transaction_repo.create.call_args[0][0]
        assert call_data.type == "expense"

    def test_positive_amount_is_categorized_as_income(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_all.return_value = [
            _make_category_info(1, "Anden"),
        ]
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)

        csv_data = self._make_csv("2024/01/15;500,00;Løn;;;Løn udbetaling")

        # Act
        service.import_from_csv(csv_data, account_id=1)

        # Assert
        call_data = mock_transaction_repo.create.call_args[0][0]
        assert call_data.type == "income"

    def test_amount_is_stored_as_absolute_value(
        self, service, mock_transaction_repo, mock_category_repo
    ):
        # Arrange
        mock_category_repo.get_all.return_value = [
            _make_category_info(1, "Anden"),
        ]
        mock_transaction_repo.create.return_value = _make_transaction_entity(tx_id=1)

        csv_data = self._make_csv("2024/01/15;-150,50;Netto;;;Netto køb")

        # Act
        service.import_from_csv(csv_data, account_id=1)

        # Assert
        call_data = mock_transaction_repo.create.call_args[0][0]
        assert call_data.amount == 150.50


# ============================================================================
# Static helpers
# ============================================================================


class TestFilterByMonthYear:
    """Tests for the _filter_by_month_year static helper."""

    def test_filters_by_month_with_date_objects(self):
        transactions = [
            _make_transaction_entity(tx_id=1, tx_date=date(2024, 1, 15)),
            _make_transaction_entity(tx_id=2, tx_date=date(2024, 2, 10)),
        ]

        result = TransactionService._filter_by_month_year(transactions, month="01", year=None)

        assert len(result) == 1

    def test_filters_by_year_with_date_objects(self):
        transactions = [
            _make_transaction_entity(tx_id=1, tx_date=date(2024, 6, 15)),
            _make_transaction_entity(tx_id=2, tx_date=date(2023, 6, 15)),
        ]

        result = TransactionService._filter_by_month_year(transactions, month=None, year="2024")

        assert len(result) == 1

    def test_skips_entries_without_date(self):
        transactions = [
            _make_transaction_entity(tx_id=1, tx_date=date(2024, 1, 15)),
            Mock(date=None),
            Mock(),  # no date attribute
        ]

        result = TransactionService._filter_by_month_year(transactions, month="01", year=None)

        assert len(result) == 1

    def test_skips_entries_with_unparseable_date(self):
        transactions = [
            Mock(date=None),
            _make_transaction_entity(tx_id=2, tx_date=date(2024, 1, 15)),
        ]

        result = TransactionService._filter_by_month_year(transactions, month="01", year=None)

        assert len(result) == 1
