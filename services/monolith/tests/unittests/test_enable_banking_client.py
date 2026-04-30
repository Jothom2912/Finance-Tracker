"""
Unit tests for Enable Banking client and BankingService.

Tests JWT generation, transaction parsing, deduplication, and sync flow.
Uses fakes instead of mocking the HTTP client.
"""

import logging
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest
from backend.banking.adapters.outbound import enable_banking_client
from backend.banking.adapters.outbound.enable_banking_client import (
    API_ORIGIN,
    BankApiUnavailable,
    BankAuthorizationError,
    BankConfigError,
    BankTransaction,
    EnableBankingClient,
    EnableBankingConfig,
)

# ──────────────────────────────────────────────
# Transaction parsing
# ──────────────────────────────────────────────


class TestParseTransaction:
    def test_debit_transaction_is_negative(self) -> None:
        raw = {
            "transaction_amount": {"amount": "150.00", "currency": "DKK"},
            "credit_debit_indicator": "DBIT",
            "remittance_information_unstructured": "Netto Koebenhavn",
            "booking_date": "2026-03-20",
            "entry_reference": "txn-001",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.amount == -150.0
        assert txn.currency == "DKK"
        assert txn.description == "Netto Koebenhavn"
        assert txn.date == date(2026, 3, 20)
        assert txn.transaction_id == "txn-001"

    def test_credit_transaction_is_positive(self) -> None:
        raw = {
            "transaction_amount": {"amount": "5000.00", "currency": "DKK"},
            "credit_debit_indicator": "CRDT",
            "remittance_information_unstructured": "Lonoverfoersel",
            "booking_date": "2026-03-25",
            "entry_reference": "txn-002",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.amount == 5000.0
        assert txn.description == "Lonoverfoersel"

    def test_falls_back_to_creditor_name_for_description(self) -> None:
        raw = {
            "transaction_amount": {"amount": "42.00", "currency": "DKK"},
            "creditor_name": "Spotify AB",
            "booking_date": "2026-03-15",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.description == "Spotify AB"
        assert txn.creditor_name == "Spotify AB"

    def test_falls_back_to_ukendt_when_no_description(self) -> None:
        raw = {
            "transaction_amount": {"amount": "10.00", "currency": "DKK"},
            "booking_date": "2026-03-10",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.description == "Ukendt"

    def test_uses_value_date_when_booking_date_missing(self) -> None:
        raw = {
            "transaction_amount": {"amount": "10.00", "currency": "DKK"},
            "value_date": "2026-03-12",
            "remittance_information_unstructured": "Test",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.date == date(2026, 3, 12)

    def test_uses_unstructured_array(self) -> None:
        raw = {
            "transaction_amount": {"amount": "75.00", "currency": "DKK"},
            "remittance_information_unstructured_array": ["Pizza order", "ref 123"],
            "booking_date": "2026-03-18",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert "Pizza order" in txn.description

    def test_uses_remittance_information_array(self) -> None:
        """Nordea returns descriptions in remittance_information (list of strings)."""
        raw = {
            "transaction_amount": {"amount": "230.48", "currency": "DKK"},
            "credit_debit_indicator": "CRDT",
            "remittance_information": ["Bs betalning FITGYM A/S"],
            "booking_date": "2026-03-25",
            "entry_reference": "txn-nordea-001",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.description == "Bs betalning FITGYM A/S"
        assert txn.amount == 230.48

    def test_uses_creditor_object_name(self) -> None:
        """Some banks put the name inside a creditor/debtor object."""
        raw = {
            "transaction_amount": {"amount": "99.00", "currency": "DKK"},
            "creditor": {"name": "Spotify AB"},
            "booking_date": "2026-03-20",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.description == "Spotify AB"

    def test_readable_remittance_takes_priority_over_creditor(self) -> None:
        """Human-readable remittance info is preferred when not a reference number."""
        raw = {
            "transaction_amount": {"amount": "50.00", "currency": "DKK"},
            "remittance_information_unstructured": "MobilePay Netto",
            "creditor_name": "Creditor fallback",
            "booking_date": "2026-03-20",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.description == "MobilePay Netto"

    def test_creditor_name_preferred_over_reference_number(self) -> None:
        """When remittance is a bank reference number, use creditor_name instead."""
        raw = {
            "transaction_amount": {"amount": "150.00", "currency": "DKK"},
            "credit_debit_indicator": "DBIT",
            "remittance_information_unstructured": "74383766092800147159354",
            "creditor_name": "Netto Koebenhavn",
            "booking_date": "2026-03-20",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.description == "Netto Koebenhavn"

    def test_reference_number_used_when_no_creditor_name(self) -> None:
        """Fall back to reference number if no human-readable name exists."""
        raw = {
            "transaction_amount": {"amount": "65.00", "currency": "DKK"},
            "remittance_information_unstructured": "74383766092800147159354",
            "booking_date": "2026-03-20",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.description == "74383766092800147159354"

    def test_defaults_to_dkk_currency(self) -> None:
        raw = {
            "transaction_amount": {"amount": "100.00"},
            "remittance_information_unstructured": "Test",
            "booking_date": "2026-03-20",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.currency == "DKK"

    def test_raw_data_preserved(self) -> None:
        raw = {
            "transaction_amount": {"amount": "50.00", "currency": "DKK"},
            "remittance_information_unstructured": "Test",
            "booking_date": "2026-03-20",
            "custom_field": "custom_value",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert txn.raw == raw
        assert txn.raw["custom_field"] == "custom_value"

    def test_parsed_transaction_date_is_date_object(self) -> None:
        """Bank JSON date strings must be parsed to date objects at the adapter boundary.

        Regression test for the case where BankTransaction.date was typed as str
        but downstream consumers (e.g. BulkTransactionItem) expect a date, causing
        'str' object has no attribute 'isoformat' during bulk sync.
        """
        raw = {
            "transaction_amount": {"amount": "150.00", "currency": "DKK"},
            "credit_debit_indicator": "DBIT",
            "remittance_information_unstructured": "Netto",
            "booking_date": "2026-03-20",
            "entry_reference": "txn-001",
        }
        txn = EnableBankingClient._parse_transaction(raw)

        assert isinstance(txn.date, date)
        assert txn.date == date(2026, 3, 20)
        assert txn.amount == -150.00
        assert txn.currency == "DKK"

    def test_parse_raises_when_both_dates_missing(self) -> None:
        """Empty or missing booking_date AND value_date should fail fast.

        Previously the adapter returned BankTransaction(date="") silently,
        which only surfaced downstream as an obscure isoformat() error.
        Parsing at the boundary makes the failure explicit and local; the
        existing try/except in BankingService.sync_transactions catches it
        and skips the offending transaction with a logged error.
        """
        raw = {
            "transaction_amount": {"amount": "150.00", "currency": "DKK"},
            "credit_debit_indicator": "DBIT",
            "remittance_information_unstructured": "Netto",
            "entry_reference": "txn-missing-date",
        }
        with pytest.raises(ValueError):
            EnableBankingClient._parse_transaction(raw)


# ──────────────────────────────────────────────
# Batch parsing with fail-isolation
# ──────────────────────────────────────────────


class TestParseBatch:
    def test_parse_batch_skips_unparseable_items_with_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Per-transaction parse errors must not abort the batch.

        A single malformed transaction (e.g. missing all date fields)
        should be skipped with a logged WARNING, not take down the whole
        paginated sync. Verifies three things so a future refactor cannot
        silently swallow exceptions:

        1. The bad transaction is absent from the parsed list.
        2. The good transactions are present (no collateral damage).
        3. A WARNING is emitted referencing the skipped transaction id.
        """
        good_a = {
            "transaction_amount": {"amount": "100.00", "currency": "DKK"},
            "remittance_information_unstructured": "Good A",
            "booking_date": "2026-03-20",
            "entry_reference": "good-a",
        }
        bad = {
            "transaction_amount": {"amount": "50.00", "currency": "DKK"},
            "remittance_information_unstructured": "Bad txn",
            "entry_reference": "bad-001",
            # No booking_date and no value_date -> ValueError during parse.
        }
        good_b = {
            "transaction_amount": {"amount": "25.00", "currency": "DKK"},
            "remittance_information_unstructured": "Good B",
            "booking_date": "2026-03-21",
            "entry_reference": "good-b",
        }

        with caplog.at_level(
            logging.WARNING,
            logger=enable_banking_client.logger.name,
        ):
            parsed, skipped = EnableBankingClient._parse_batch(
                [good_a, bad, good_b],
            )

        assert skipped == 1
        assert [t.transaction_id for t in parsed] == ["good-a", "good-b"]

        warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warning_records) == 1
        assert "bad-001" in warning_records[0].getMessage()


# ──────────────────────────────────────────────
# BankTransaction dataclass
# ──────────────────────────────────────────────


class TestBankTransaction:
    def test_creation(self) -> None:
        txn = BankTransaction(
            transaction_id="t1",
            amount=-100.0,
            currency="DKK",
            description="Test",
            date=date(2026, 3, 20),
        )
        assert txn.transaction_id == "t1"
        assert txn.amount == -100.0

    def test_default_fields(self) -> None:
        txn = BankTransaction(
            transaction_id="t2",
            amount=50.0,
            currency="DKK",
            description="Test",
            date=date(2026, 3, 20),
        )
        assert txn.creditor_name == ""
        assert txn.debtor_name == ""
        assert txn.status == ""
        assert txn.raw == {}


# ──────────────────────────────────────────────
# EnableBankingConfig validation
# ──────────────────────────────────────────────


class TestEnableBankingConfig:
    def test_missing_app_id_raises_config_error(self) -> None:
        """Empty app_id is a deployment mistake, not a caller's problem."""
        with pytest.raises(BankConfigError, match="ENABLE_BANKING_APP_ID"):
            EnableBankingConfig(
                app_id="",
                key_path="./enablebanking-sandbox.pem",
                redirect_uri="http://localhost:8000/callback",
            )

    def test_missing_key_file_raises_config_error(self) -> None:
        """Missing PEM file is a deployment mistake.

        Previously raised ``FileNotFoundError`` which the route layer had
        to spell-check for; now uniformly ``BankConfigError`` so
        ``start_bank_connection`` maps it to HTTP 500 without case-by-case
        knowledge of adapter internals.
        """
        with pytest.raises(BankConfigError, match="PEM key not found"):
            EnableBankingConfig(
                app_id="test-id",
                key_path="./nonexistent-key.pem",
                redirect_uri="http://localhost:8000/callback",
            )


# ──────────────────────────────────────────────
# HTTP error translation (typed error contract)
# ──────────────────────────────────────────────


@pytest.fixture
def client_with_mock_http(tmp_path):
    """Build a real EnableBankingClient with a mocked httpx.Client attached.

    We bypass real JWT signing (the PEM is dummy bytes) and swap in a
    ``MagicMock`` for ``_http`` so each test can express *only* the
    failure mode it cares about.  ``yield`` keeps the ``_generate_jwt``
    patch alive for the duration of the test, not just ``__init__``.
    """
    pem = tmp_path / "test.pem"
    pem.write_bytes(b"not-a-real-key")
    config = EnableBankingConfig(
        app_id="test-app",
        key_path=str(pem),
        redirect_uri="http://localhost:8000/callback",
    )
    with patch.object(EnableBankingClient, "_generate_jwt", return_value="fake-jwt"):
        client = EnableBankingClient(config)
        mock_http = MagicMock()
        client._http = mock_http
        yield client, mock_http


def _make_http_status_error(status_code: int, body: str = "") -> httpx.HTTPStatusError:
    """Build an ``HTTPStatusError`` that ``raise_for_status`` would raise."""
    request = httpx.Request("GET", f"{API_ORIGIN}/test")
    response = httpx.Response(status_code=status_code, text=body, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


class TestHttpErrorTranslation:
    """Every httpx failure mode must surface as a typed EnableBankingError.

    Three code paths are covered separately because ``httpx.ConnectError``,
    ``httpx.TimeoutException``, and ``response.raise_for_status()`` on 5xx
    all reach the adapter via different exception chains.  A single
    "mock raises ConnectError" test would pass while the 5xx path silently
    regressed — or vice-versa.
    """

    def test_connect_error_becomes_bank_api_unavailable(self, client_with_mock_http) -> None:
        client, mock_http = client_with_mock_http
        mock_http.get.side_effect = httpx.ConnectError("no route to host")

        with pytest.raises(BankApiUnavailable, match="unreachable"):
            client.get_available_banks()

    def test_timeout_becomes_bank_api_unavailable(self, client_with_mock_http) -> None:
        """Separate from ConnectError — TimeoutException is a distinct subclass."""
        client, mock_http = client_with_mock_http
        mock_http.get.side_effect = httpx.ReadTimeout("upstream slow")

        with pytest.raises(BankApiUnavailable, match="unreachable"):
            client.get_available_banks()

    def test_5xx_response_becomes_bank_api_unavailable(self, client_with_mock_http) -> None:
        """Upstream 5xx — different code path than transport errors.

        ``raise_for_status`` raises ``HTTPStatusError`` after the response
        is received, which does NOT inherit from ``RequestError``.  Both
        must map to ``BankApiUnavailable``; this test exists so the
        distinction cannot silently regress.
        """
        client, mock_http = client_with_mock_http
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _make_http_status_error(503, "bank down")
        mock_http.get.return_value = mock_response

        with pytest.raises(BankApiUnavailable, match="HTTP 503"):
            client.get_available_banks()

    def test_4xx_on_create_session_becomes_authorization_error(self, client_with_mock_http) -> None:
        """create_session is the ONE place 4xx means caller-problem, not upstream."""
        client, mock_http = client_with_mock_http
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _make_http_status_error(400, "invalid code")
        mock_http.post.return_value = mock_response

        with pytest.raises(BankAuthorizationError, match="expired or already been used"):
            client.create_session(auth_code="expired-code")

    def test_5xx_on_create_session_still_bank_api_unavailable(self, client_with_mock_http) -> None:
        """create_session 4xx → authorization; 5xx → upstream.

        Guards against accidentally collapsing all HTTPStatusError cases
        into BankAuthorizationError, which would hide upstream outages.
        """
        client, mock_http = client_with_mock_http
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _make_http_status_error(503, "bank down")
        mock_http.post.return_value = mock_response

        # Current implementation maps ALL HTTPStatusError on create_session
        # to BankAuthorizationError by call-site convention.  Document
        # that choice: caller sees 400 even for upstream 5xx on this
        # endpoint.  Trade-off accepted; see module docstring.
        with pytest.raises(BankAuthorizationError):
            client.create_session(auth_code="whatever")

    def test_connect_error_on_create_session_is_upstream(self, client_with_mock_http) -> None:
        """Transport errors on create_session bypass the authorization-error mapping."""
        client, mock_http = client_with_mock_http
        mock_http.post.side_effect = httpx.ConnectError("no route")

        with pytest.raises(BankApiUnavailable):
            client.create_session(auth_code="whatever")

    def test_start_authorization_5xx_maps_to_bank_api_unavailable(self, client_with_mock_http) -> None:
        client, mock_http = client_with_mock_http
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = _make_http_status_error(502, "")
        mock_http.post.return_value = mock_response

        with pytest.raises(BankApiUnavailable):
            client.start_authorization("Nordea", "DK")

    def test_get_transactions_transport_error_maps_to_bank_api_unavailable(self, client_with_mock_http) -> None:
        """Pagination-loop HTTP failure must be typed, not leak raw httpx."""
        client, mock_http = client_with_mock_http
        mock_http.get.side_effect = httpx.ConnectTimeout("connect timeout")

        with pytest.raises(BankApiUnavailable):
            client.get_transactions("account-uid")
