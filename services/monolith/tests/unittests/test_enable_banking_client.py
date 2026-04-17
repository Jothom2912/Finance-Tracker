"""
Unit tests for Enable Banking client and BankingService.

Tests JWT generation, transaction parsing, deduplication, and sync flow.
Uses fakes instead of mocking the HTTP client.
"""

import logging
from datetime import date

import pytest

from backend.banking.adapters.outbound import enable_banking_client
from backend.banking.adapters.outbound.enable_banking_client import (
    BankTransaction,
    EnableBankingClient,
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
    def test_parse_batch_skips_unparseable_items_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
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
            logging.WARNING, logger=enable_banking_client.logger.name,
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
    def test_missing_app_id_raises(self) -> None:
        from backend.banking.adapters.outbound.enable_banking_client import (
            EnableBankingConfig,
        )
        with pytest.raises(ValueError, match="ENABLE_BANKING_APP_ID"):
            EnableBankingConfig(
                app_id="",
                key_path="./enablebanking-sandbox.pem",
                redirect_uri="http://localhost:8000/callback",
            )

    def test_missing_key_file_raises(self) -> None:
        from backend.banking.adapters.outbound.enable_banking_client import (
            EnableBankingConfig,
        )
        with pytest.raises(FileNotFoundError):
            EnableBankingConfig(
                app_id="test-id",
                key_path="./nonexistent-key.pem",
                redirect_uri="http://localhost:8000/callback",
            )
