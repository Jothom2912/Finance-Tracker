from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from app.application.csv_parsers.base import ParsedCSVResult
from app.application.csv_parsers.internal import InternalCSVParser
from app.application.csv_parsers.registry import get_parser
from app.domain.exceptions import CSVImportException


class TestInternalCSVParser:
    def setup_method(self) -> None:
        self.parser = InternalCSVParser()

    def test_parse_valid_row(self) -> None:
        content = (
            b"date,amount,transaction_type,account_id,account_name,"
            b"category_id,category_name,description\n"
            b"2026-03-01,49.99,expense,100,Main Account,5,Food,Groceries\n"
        )

        result = self.parser.parse(content, user_id=10, account_id=0, account_name="")

        assert isinstance(result, ParsedCSVResult)
        assert len(result.rows) == 1
        assert result.skipped == 0
        assert result.errors == []

        row = result.rows[0]
        assert row["user_id"] == 10
        assert row["account_id"] == 100
        assert row["account_name"] == "Main Account"
        assert row["amount"] == Decimal("49.99")
        assert row["transaction_type"] == "expense"
        assert row["tx_date"] == date(2026, 3, 1)
        assert row["category_id"] == 5
        assert row["category_name"] == "Food"
        assert row["description"] == "Groceries"

    def test_parse_minimal_required_columns(self) -> None:
        content = b"date,amount,transaction_type,account_id,account_name\n2026-06-15,100.00,income,1,Savings\n"

        result = self.parser.parse(content, user_id=1, account_id=0, account_name="")

        assert len(result.rows) == 1
        assert result.rows[0]["category_id"] is None
        assert result.rows[0]["category_name"] is None
        assert result.rows[0]["description"] is None

    def test_parse_multiple_rows(self) -> None:
        content = (
            b"date,amount,transaction_type,account_id,account_name\n"
            b"2026-01-01,10.00,expense,1,A\n"
            b"2026-01-02,20.00,income,2,B\n"
            b"2026-01-03,30.00,expense,3,C\n"
        )

        result = self.parser.parse(content, user_id=5, account_id=0, account_name="")

        assert len(result.rows) == 3
        assert result.skipped == 0

    def test_parse_malformed_amount_is_lenient(self) -> None:
        content = (
            b"date,amount,transaction_type,account_id,account_name\n"
            b"2026-03-01,49.99,expense,100,OK\n"
            b"2026-03-01,INVALID,expense,100,Bad\n"
        )

        result = self.parser.parse(content, user_id=10, account_id=0, account_name="")

        assert len(result.rows) == 1
        assert result.skipped == 1
        assert len(result.errors) == 1
        assert "Row 3" in result.errors[0]

    def test_parse_negative_amount_is_error(self) -> None:
        content = b"date,amount,transaction_type,account_id,account_name\n2026-03-01,-50.00,expense,100,Acct\n"

        result = self.parser.parse(content, user_id=10, account_id=0, account_name="")

        assert len(result.rows) == 0
        assert result.skipped == 1
        assert "Row 2" in result.errors[0]

    def test_parse_invalid_transaction_type(self) -> None:
        content = b"date,amount,transaction_type,account_id,account_name\n2026-03-01,50.00,transfer,100,Acct\n"

        result = self.parser.parse(content, user_id=10, account_id=0, account_name="")

        assert len(result.rows) == 0
        assert result.skipped == 1
        assert "invalid transaction_type" in result.errors[0]

    def test_empty_file_raises(self) -> None:
        with pytest.raises(CSVImportException, match="empty or has no headers"):
            self.parser.parse(b"", user_id=10, account_id=0, account_name="")

    def test_missing_required_columns_raises(self) -> None:
        content = b"date,amount\n2026-01-01,10.00\n"

        with pytest.raises(CSVImportException, match="missing required columns"):
            self.parser.parse(content, user_id=10, account_id=0, account_name="")

    def test_header_only_returns_empty(self) -> None:
        content = b"date,amount,transaction_type,account_id,account_name\n"

        result = self.parser.parse(content, user_id=10, account_id=0, account_name="")

        assert len(result.rows) == 0
        assert result.skipped == 0
        assert result.errors == []

    def test_ignores_account_params(self) -> None:
        """Internal format reads account from CSV rows, not from parameters."""
        content = b"date,amount,transaction_type,account_id,account_name\n2026-01-01,10.00,expense,42,FromCSV\n"

        result = self.parser.parse(content, user_id=1, account_id=999, account_name="Ignored")

        assert result.rows[0]["account_id"] == 42
        assert result.rows[0]["account_name"] == "FromCSV"


class TestParserRegistry:
    def test_get_internal_parser(self) -> None:
        parser = get_parser("internal")
        assert isinstance(parser, InternalCSVParser)

    def test_unknown_format_raises(self) -> None:
        with pytest.raises(CSVImportException, match="Unknown bank format"):
            get_parser("nonexistent")

    def test_error_lists_supported_formats(self) -> None:
        with pytest.raises(CSVImportException, match="internal"):
            get_parser("bad")
