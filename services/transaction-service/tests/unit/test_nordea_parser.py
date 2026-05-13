from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest
from app.application.csv_parsers.nordea import NordeaCSVParser
from app.application.csv_parsers.utils import parse_danish_amount
from app.domain.exceptions import CSVImportException

FIXTURES = Path(__file__).parent / "fixtures"

USER_ID = 10
ACCOUNT_ID = 42
ACCOUNT_NAME = "Min Nordea Konto"


class TestNordeaGoldenFile:
    """Golden-file test: parse the real sample and verify every row."""

    def setup_method(self) -> None:
        self.parser = NordeaCSVParser()
        self.content = (FIXTURES / "nordea_sample.csv").read_bytes()

    def test_row_count(self) -> None:
        result = self.parser.parse(self.content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 6
        assert result.skipped == 0
        assert result.errors == []

    def test_expense_row(self) -> None:
        result = self.parser.parse(self.content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[0]
        assert row["tx_date"] == date(2026, 2, 26)
        assert row["amount"] == Decimal("35.00")
        assert row["transaction_type"] == "expense"
        assert row["description"] == "KEA V/ SIMPLY COOKING A/S"
        assert row["account_id"] == ACCOUNT_ID
        assert row["account_name"] == ACCOUNT_NAME
        assert row["user_id"] == USER_ID
        assert row["category_id"] is None
        assert row["category_name"] is None

    def test_income_row_with_modtager(self) -> None:
        """Row 4: positive amount, Modtager is set, Navn has the MobilePay info."""
        result = self.parser.parse(self.content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[2]
        assert row["tx_date"] == date(2026, 2, 23)
        assert row["amount"] == Decimal("200.00")
        assert row["transaction_type"] == "income"
        assert row["description"] == "MobilePay Adam Fischer Duffus"

    def test_income_empty_navn(self) -> None:
        """Row 5: income, Navn is empty, Beskrivelse has 'Fra Opsparing'."""
        result = self.parser.parse(self.content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[3]
        assert row["tx_date"] == date(2026, 2, 20)
        assert row["amount"] == Decimal("500.00")
        assert row["transaction_type"] == "income"
        assert row["description"] == "Fra Opsparing"

    def test_expense_empty_navn_uses_beskrivelse(self) -> None:
        """Row 6: expense, Navn is empty, Beskrivelse has 'Cph Village'."""
        result = self.parser.parse(self.content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[4]
        assert row["tx_date"] == date(2026, 2, 2)
        assert row["amount"] == Decimal("5560.00")
        assert row["transaction_type"] == "expense"
        assert row["description"] == "Cph Village"

    def test_large_income(self) -> None:
        """Row 7: SU payment of 6281,00."""
        result = self.parser.parse(self.content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[5]
        assert row["tx_date"] == date(2026, 1, 30)
        assert row["amount"] == Decimal("6281.00")
        assert row["transaction_type"] == "income"
        assert row["description"] == "SU"

    def test_decimal_precision(self) -> None:
        """Row 2 has -145,08 -- verify two-decimal precision survives."""
        result = self.parser.parse(self.content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        row = result.rows[1]
        assert row["amount"] == Decimal("145.08")


class TestNordeaEncoding:
    def setup_method(self) -> None:
        self.parser = NordeaCSVParser()

    def test_utf8_with_bom(self) -> None:
        content = (
            b"\xef\xbb\xbf"
            b"Bogf\xc3\xb8ringsdato;Bel\xc3\xb8b;Afsender;Modtager;"
            b"Navn;Beskrivelse;Saldo;Valuta;Afstemt;\n"
            b"2026/01/01;-100,00;123;;NETTO;NETTO;900,00;DKK;;\n"
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 1
        assert result.rows[0]["amount"] == Decimal("100.00")

    def test_latin1_fallback(self) -> None:
        header = "Bogføringsdato;Beløb;Afsender;Modtager;Navn;Beskrivelse;Saldo;Valuta;Afstemt;\n"
        data = "2026/01/01;-50,00;123;;NETTO;NETTO;950,00;DKK;;\n"
        content = (header + data).encode("windows-1252")
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 1
        assert result.rows[0]["amount"] == Decimal("50.00")

    def test_plain_utf8_no_bom(self) -> None:
        content = (
            "Bogføringsdato;Beløb;Afsender;Modtager;"
            "Navn;Beskrivelse;Saldo;Valuta;Afstemt;\n"
            "2026/03/01;-25,00;123;;Shop;Shop;100,00;DKK;;\n"
        ).encode("utf-8")
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 1


class TestNordeaEdgeCases:
    def setup_method(self) -> None:
        self.parser = NordeaCSVParser()

    def _make_csv(self, *data_lines: str) -> bytes:
        header = "Bogføringsdato;Beløb;Afsender;Modtager;Navn;Beskrivelse;Saldo;Valuta;Afstemt;\n"
        body = "\n".join(data_lines) + "\n" if data_lines else ""
        return (header + body).encode("utf-8")

    def test_empty_file_raises(self) -> None:
        with pytest.raises(CSVImportException, match="empty or has no headers"):
            self.parser.parse(b"", USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

    def test_header_only_returns_empty(self) -> None:
        content = self._make_csv()
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 0
        assert result.skipped == 0

    def test_missing_required_column_raises(self) -> None:
        content = b"Bogf\xc3\xb8ringsdato;Afsender;Modtager\n2026/01/01;123;456\n"
        with pytest.raises(CSVImportException, match="missing required columns"):
            self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)

    def test_malformed_amount_is_lenient(self) -> None:
        content = self._make_csv(
            "2026/01/01;-100,00;123;;OK;OK;900,00;DKK;;",
            "2026/01/02;BOGUS;123;;Bad;Bad;900,00;DKK;;",
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 1
        assert result.skipped == 1
        assert "Row 3" in result.errors[0]

    def test_zero_amount_is_skipped(self) -> None:
        content = self._make_csv(
            "2026/01/01;0,00;123;;Zero;Zero;1000,00;DKK;;",
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 0
        assert result.skipped == 1
        assert "amount is zero" in result.errors[0]

    def test_malformed_date_is_lenient(self) -> None:
        content = self._make_csv(
            "not-a-date;-50,00;123;;Shop;Shop;950,00;DKK;;",
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 0
        assert result.skipped == 1
        assert "Row 2" in result.errors[0]

    def test_empty_rows_between_data(self) -> None:
        header = "Bogføringsdato;Beløb;Afsender;Modtager;Navn;Beskrivelse;Saldo;Valuta;Afstemt;\n"
        body = "2026/01/01;-10,00;123;;A;A;990,00;DKK;;\n\n2026/01/02;-20,00;123;;B;B;970,00;DKK;;\n"
        content = (header + body).encode("utf-8")
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 2
        assert result.rows[0]["description"] == "A"
        assert result.rows[1]["description"] == "B"

    def test_both_navn_and_beskrivelse_empty_uses_placeholder(self) -> None:
        content = self._make_csv(
            "2026/01/01;-100,00;123;;;;1000,00;DKK;;",
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 1
        assert result.rows[0]["description"] == "(no description)"

    def test_beskrivelse_preferred_over_navn(self) -> None:
        content = self._make_csv(
            "2026/01/01;-100,00;123;;StoreName;Payment for X;900,00;DKK;;",
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert result.rows[0]["description"] == "Payment for X"

    def test_fallback_to_navn_when_beskrivelse_empty(self) -> None:
        content = self._make_csv(
            "2026/01/01;-100,00;123;;StoreName;;900,00;DKK;;",
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert result.rows[0]["description"] == "StoreName"

    def test_trailing_semicolons_handled(self) -> None:
        """Nordea exports have a trailing ; creating a ghost empty column."""
        content = self._make_csv(
            "2026/01/01;-30,00;123;;Shop;Shop;970,00;DKK;;",
        )
        result = self.parser.parse(content, USER_ID, ACCOUNT_ID, ACCOUNT_NAME)
        assert len(result.rows) == 1

    def test_uses_account_from_parameters(self) -> None:
        content = self._make_csv(
            "2026/01/01;-10,00;9999;;Shop;Shop;100,00;DKK;;",
        )
        result = self.parser.parse(content, 7, 55, "Test Konto")
        assert result.rows[0]["user_id"] == 7
        assert result.rows[0]["account_id"] == 55
        assert result.rows[0]["account_name"] == "Test Konto"


class TestParseDanishAmount:
    """Unit tests for the Danish number parsing helper."""

    def test_simple_negative(self) -> None:
        assert parse_danish_amount("-35,00") == Decimal("-35.00")

    def test_simple_positive(self) -> None:
        assert parse_danish_amount("500,00") == Decimal("500.00")

    def test_thousands_separator(self) -> None:
        assert parse_danish_amount("1.234,56") == Decimal("1234.56")

    def test_negative_with_thousands(self) -> None:
        assert parse_danish_amount("-12.345,67") == Decimal("-12345.67")

    def test_large_with_thousands(self) -> None:
        assert parse_danish_amount("1.000.000,00") == Decimal("1000000.00")

    def test_integer_no_separators(self) -> None:
        assert parse_danish_amount("100") == Decimal("100")

    def test_english_format_passthrough(self) -> None:
        assert parse_danish_amount("35.00") == Decimal("35.00")

    def test_whitespace_stripped(self) -> None:
        assert parse_danish_amount("  -50,00  ") == Decimal("-50.00")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty amount"):
            parse_danish_amount("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty amount"):
            parse_danish_amount("   ")

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(InvalidOperation):
            parse_danish_amount("abc")

    def test_one_thousand_exact(self) -> None:
        """1.000 with no comma -- treated as English decimal (1.0).
        This is an inherent ambiguity; with no comma present,
        the period is treated as a decimal point.
        """
        assert parse_danish_amount("1.000") == Decimal("1.000")

    def test_one_thousand_with_decimals(self) -> None:
        """1.000,50 -- period is thousands, comma is decimal."""
        assert parse_danish_amount("1.000,50") == Decimal("1000.50")
