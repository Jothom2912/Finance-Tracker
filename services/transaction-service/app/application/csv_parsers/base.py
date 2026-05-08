from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


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


class BankCSVParser(Protocol):
    """Contract that every bank-format CSV parser must satisfy."""

    def parse(
        self,
        file_content: bytes,
        user_id: int,
        account_id: int,
        account_name: str,
    ) -> ParsedCSVResult: ...
