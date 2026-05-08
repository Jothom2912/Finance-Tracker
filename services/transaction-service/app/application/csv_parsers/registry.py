from __future__ import annotations

from app.application.csv_parsers.base import BankCSVParser
from app.application.csv_parsers.danske_bank import DanskeBankCSVParser
from app.application.csv_parsers.internal import InternalCSVParser
from app.application.csv_parsers.nordea import NordeaCSVParser
from app.domain.exceptions import CSVImportException

_PARSERS: dict[str, BankCSVParser] = {
    "internal": InternalCSVParser(),
    "nordea": NordeaCSVParser(),
    "danske_bank": DanskeBankCSVParser(),
}


def get_parser(bank_format: str) -> BankCSVParser:
    """Look up a CSV parser by bank format identifier.

    Raises :class:`CSVImportException` for unknown formats.
    """
    parser = _PARSERS.get(bank_format)
    if parser is None:
        supported = ", ".join(sorted(_PARSERS))
        raise CSVImportException(
            f"Unknown bank format: {bank_format!r}. "
            f"Supported formats: {supported}"
        )
    return parser
