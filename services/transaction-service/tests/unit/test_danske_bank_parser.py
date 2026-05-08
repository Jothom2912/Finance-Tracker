from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from app.application.csv_parsers.danske_bank import DanskeBankCSVParser
from app.domain.exceptions import CSVImportException

FIXTURES = Path(__file__).parent / "fixtures"

USER_ID = 10
ACCOUNT_ID = 42
ACCOUNT_NAME = "Min Danske Konto"


@pytest.fixture
def parser():
    return DanskeBankCSVParser()


def _make_csv(*rows: str, encoding: str = "windows-1252") -> bytes:
    header = '"Dato";"Kategori";"Underkategori";"Tekst";"Bel\u00f8b";"Saldo";"Status";"Afstemt"'
    body = "\r\n".join([header, *rows])
    return body.encode(encoding)


class TestDanskeBankGoldenFile:
    """Verify parser against the anonymized real-data sample."""

    def test_golden_file_parses_all_rows(self, parser):
        data = (FIXTURES / "danske_bank_sample.csv").read_bytes()
        result = parser.parse(data, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 6
        assert result.skipped == 0
        assert result.errors == []

    def test_golden_file_first_row_income(self, parser):
        data = (FIXTURES / "danske_bank_sample.csv").read_bytes()
        result = parser.parse(data, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[0]

        assert row["tx_date"] == date(2026, 4, 8)
        assert row["amount"] == Decimal("100.00")
        assert row["transaction_type"] == "income"
        assert row["description"] == "MobilePay Test Person"
        assert row["user_id"] == USER_ID
        assert row["account_id"] == ACCOUNT_ID
        assert row["account_name"] == ACCOUNT_NAME

    def test_golden_file_thousands_separator(self, parser):
        data = (FIXTURES / "danske_bank_sample.csv").read_bytes()
        result = parser.parse(data, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[1]

        assert row["amount"] == Decimal("1000.00")
        assert row["transaction_type"] == "income"

    def test_golden_file_expense_row(self, parser):
        data = (FIXTURES / "danske_bank_sample.csv").read_bytes()
        result = parser.parse(data, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[2]

        assert row["tx_date"] == date(2026, 4, 13)
        assert row["amount"] == Decimal("90.00")
        assert row["transaction_type"] == "expense"
        assert row["description"] == "Restaurant ABC"

    def test_golden_file_decimal_amount(self, parser):
        data = (FIXTURES / "danske_bank_sample.csv").read_bytes()
        result = parser.parse(data, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[3]

        assert row["amount"] == Decimal("98.42")
        assert row["transaction_type"] == "expense"

    def test_golden_file_pending_rows_included(self, parser):
        """Rows with Status='Venter' and empty Saldo are still parsed."""
        data = (FIXTURES / "danske_bank_sample.csv").read_bytes()
        result = parser.parse(data, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        pending_expense = result.rows[4]
        assert pending_expense["amount"] == Decimal("328.00")
        assert pending_expense["transaction_type"] == "expense"

        pending_income = result.rows[5]
        assert pending_income["amount"] == Decimal("53.50")
        assert pending_income["transaction_type"] == "income"


class TestDanskeBankEncoding:
    def test_windows_1252_decodes_correctly(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Kat";"Sub";"Caf\u00e9 \u00d8sterbro";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
            encoding="windows-1252",
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 1
        assert result.rows[0]["description"] == "Caf\u00e9 \u00d8sterbro"

    def test_utf8_also_works(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Kat";"Sub";"Caf\u00e9 \u00d8sterbro";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
            encoding="utf-8",
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 1
        assert result.rows[0]["description"] == "Caf\u00e9 \u00d8sterbro"

    def test_utf8_with_bom_also_works(self, parser):
        csv_bytes = b"\xef\xbb\xbf" + _make_csv(
            '"10.04.2026";"Kat";"Sub";"Test";"-25,00";"100,00";"Udf\u00f8rt";"Nej"',
            encoding="utf-8",
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 1


class TestDanskeBankEdgeCases:
    def test_empty_file_raises(self, parser):
        with pytest.raises(CSVImportException, match="empty"):
            parser.parse(b"", USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

    def test_header_only_returns_empty(self, parser):
        csv_bytes = _make_csv()
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 0
        assert result.skipped == 0

    def test_missing_required_column_raises(self, parser):
        bad_header = '"Dato";"Kategori";"Underkategori";"Saldo";"Status";"Afstemt"'
        csv_bytes = bad_header.encode("windows-1252")
        with pytest.raises(CSVImportException, match="missing required columns"):
            parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

    def test_zero_amount_skipped(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Kat";"Sub";"Zero tx";"0,00";"100,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 0
        assert result.skipped == 1
        assert "zero" in result.errors[0].lower()

    def test_malformed_date_skipped(self, parser):
        csv_bytes = _make_csv(
            '"not-a-date";"Kat";"Sub";"Bad date";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 0
        assert result.skipped == 1

    def test_malformed_amount_skipped(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Kat";"Sub";"Bad amount";"abc";"100,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 0
        assert result.skipped == 1

    def test_empty_description_gets_fallback(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Kat";"Sub";"";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert result.rows[0]["description"] == "(no description)"

    def test_whitespace_only_description_gets_fallback(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Kat";"Sub";"   ";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert result.rows[0]["description"] == "(no description)"

    def test_mixed_valid_and_invalid_rows(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Kat";"Sub";"Good row";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
            '"bad-date";"Kat";"Sub";"Bad row";"-25,00";"75,00";"Udf\u00f8rt";"Nej"',
            '"12.04.2026";"Kat";"Sub";"Good row 2";"-30,00";"45,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert len(result.rows) == 2
        assert result.skipped == 1
        assert len(result.errors) == 1

    def test_trailing_whitespace_in_fields_stripped(self, parser):
        csv_bytes = _make_csv(
            '"10.04.2026";"Dagligvarer                  ";"Supermarked                  ";"REMA 1000   ";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert result.rows[0]["description"] == "REMA 1000"

    def test_category_fields_not_included_in_output(self, parser):
        """Parser does not map Danske Bank categories to our category system."""
        csv_bytes = _make_csv(
            '"10.04.2026";"Dagligvarer";"Supermarked";"Shop";"-50,00";"100,00";"Udf\u00f8rt";"Nej"',
        )
        result = parser.parse(csv_bytes, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

        assert result.rows[0]["category_id"] is None
        assert result.rows[0]["category_name"] is None
