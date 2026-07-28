from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.config import settings
from app.domain.exceptions import CSVImportException


@dataclass
class ParsedCSVResult:
    """Outcome of parsing a bank CSV file.

    ``rows`` contains dicts ready for ``ITransactionRepository.bulk_create``.
    ``errors`` holds per-row error messages (e.g. "Row 3: invalid amount").
    ``skipped`` is the count of rows that could not be parsed.
    """

    rows: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: int = 0

    def add_row(self, row: dict) -> None:
        """Append a parsed row, enforcing the row cap (P2-29).

        Every parser appends through here rather than touching ``rows``
        directly, so the cap has one implementation instead of three. It is
        checked *during* parsing on purpose: enforcing it afterwards would let
        the list grow unbounded first, which is the thing being prevented.

        The cap also bounds what ``import_csv`` commits — one ``bulk_create``
        plus one outbox batch in a single transaction.
        """
        if len(self.rows) >= settings.CSV_MAX_ROWS:
            # Danish thousands separator is ".", so format explicitly rather
            # than letting f-string ",": render 50,000 into a Danish message.
            limit = f"{settings.CSV_MAX_ROWS:,}".replace(",", ".")
            raise CSVImportException(
                f"CSV-filen har for mange rækker (grænsen er {limit} rækker). Del filen op i flere mindre importer."
            )
        self.rows.append(row)


class BankCSVParser(Protocol):
    """Contract that every bank-format CSV parser must satisfy."""

    def parse(
        self,
        file_content: bytes,
        user_id: int,
        account_id: int,
        account_name: str,
    ) -> ParsedCSVResult: ...
