from __future__ import annotations

import csv
import io
from datetime import date
from decimal import InvalidOperation

from app.application.csv_parsers.base import ParsedCSVResult
from app.application.csv_parsers.utils import parse_danish_amount

_REQUIRED_COLUMNS = {"Dato", "Beløb", "Tekst"}


class DanskeBankCSVParser:
    """Parser for Danske Bank netbank CSV exports.

    Expected format:
    - Encoding: Windows-1252 (no BOM)
    - Separator: semicolon
    - Quoting: all fields double-quoted
    - Columns: Dato;Kategori;Underkategori;Tekst;Beløb;Saldo;Status;Afstemt
    - Date format: DD.MM.YYYY
    - Amount: signed, Danish decimal format (comma as decimal separator)
    - Kategori/Underkategori: padded with trailing whitespace
    """

    def parse(
        self,
        file_content: bytes,
        user_id: int,
        account_id: int,
        account_name: str,
    ) -> ParsedCSVResult:
        text = self._decode(file_content)
        reader = csv.DictReader(io.StringIO(text), delimiter=";")

        if reader.fieldnames is None:
            from app.domain.exceptions import CSVImportException

            raise CSVImportException("CSV file is empty or has no headers")

        headers = {h.strip() for h in reader.fieldnames if h and h.strip()}
        missing = _REQUIRED_COLUMNS - headers
        if missing:
            from app.domain.exceptions import CSVImportException

            raise CSVImportException(
                f"Danske Bank CSV missing required columns: "
                f"{', '.join(sorted(missing))}"
            )

        result = ParsedCSVResult()

        for row_num, row in enumerate(reader, start=2):
            if not any(v and v.strip() for v in row.values()):
                continue

            try:
                tx_date = self._parse_date(row["Dato"])
                amount = parse_danish_amount(row["Beløb"])

                if amount == 0:
                    raise ValueError("amount is zero, skipped")

                tx_type = "expense" if amount < 0 else "income"
                abs_amount = abs(amount)

                description = (row.get("Tekst") or "").strip()
                if not description:
                    description = "(no description)"

                result.rows.append(
                    {
                        "user_id": user_id,
                        "account_id": account_id,
                        "account_name": account_name,
                        "category_id": None,
                        "category_name": None,
                        "amount": abs_amount,
                        "transaction_type": tx_type,
                        "description": description,
                        "tx_date": tx_date,
                    }
                )
            except (ValueError, KeyError, InvalidOperation) as exc:
                result.errors.append(f"Row {row_num}: {exc}")
                result.skipped += 1

        return result

    @staticmethod
    def _decode(content: bytes) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return content.decode("windows-1252")

    @staticmethod
    def _parse_date(raw: str) -> date:
        """Parse DD.MM.YYYY into a :class:`date`."""
        stripped = raw.strip()
        parts = stripped.split(".")
        if len(parts) != 3:
            raise ValueError(f"invalid date format: {stripped!r}")
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        return date(year, month, day)
