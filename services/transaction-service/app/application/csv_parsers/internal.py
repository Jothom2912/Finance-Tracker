from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation

from app.application.csv_parsers.base import ParsedCSVResult

_REQUIRED_COLUMNS = {
    "date",
    "amount",
    "transaction_type",
    "account_id",
    "account_name",
}


class InternalCSVParser:
    """Parser for the internal (English column names) CSV format.

    Account information is read from each CSV row, so the ``account_id``
    and ``account_name`` parameters passed to :meth:`parse` are ignored.
    """

    def parse(
        self,
        file_content: bytes,
        user_id: int,
        account_id: int,
        account_name: str,
    ) -> ParsedCSVResult:
        text = file_content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None:
            from app.domain.exceptions import CSVImportException

            raise CSVImportException("CSV file is empty or has no headers")

        missing = _REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            from app.domain.exceptions import CSVImportException

            raise CSVImportException(
                f"CSV missing required columns: {', '.join(sorted(missing))}"
            )

        result = ParsedCSVResult()

        for row_num, row in enumerate(reader, start=2):
            try:
                amount = Decimal(row["amount"])
                if amount <= 0:
                    raise ValueError("amount must be positive")

                tx_type = row["transaction_type"].strip().lower()
                if tx_type not in ("income", "expense"):
                    raise ValueError(f"invalid transaction_type: {tx_type}")

                result.rows.append(
                    {
                        "user_id": user_id,
                        "account_id": int(row["account_id"]),
                        "account_name": row["account_name"].strip(),
                        "category_id": (
                            int(row["category_id"])
                            if row.get("category_id")
                            else None
                        ),
                        "category_name": (
                            row.get("category_name", "").strip() or None
                        ),
                        "amount": amount,
                        "transaction_type": tx_type,
                        "description": (
                            row.get("description", "").strip() or None
                        ),
                        "tx_date": date.fromisoformat(row["date"].strip()),
                    }
                )
            except (ValueError, KeyError, InvalidOperation) as exc:
                result.errors.append(f"Row {row_num}: {exc}")
                result.skipped += 1

        return result
