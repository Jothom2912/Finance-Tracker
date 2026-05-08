from __future__ import annotations

from decimal import Decimal


def parse_danish_amount(raw: str) -> Decimal:
    """Parse a Danish-formatted number into a :class:`Decimal`.

    Handles four cases:
    1. Both '.' and ',': period is thousands sep, comma is decimal
       ``"1.234,56"`` -> ``Decimal("1234.56")``
    2. Only ',': comma is decimal
       ``"-35,00"`` -> ``Decimal("-35.00")``
    3. Only '.': period is decimal (unlikely but harmless)
       ``"35.00"`` -> ``Decimal("35.00")``
    4. Neither: integer
       ``"100"`` -> ``Decimal("100")``

    Limitation: ``"1.000"`` (period, no comma) is parsed as 1.0, not
    1000.  This is safe for Nordea and Danske Bank exports where amounts
    always include decimal places (e.g. ``"6281,00"``).  If reused in a
    context where bare thousands without decimals can occur, this
    heuristic will produce incorrect results.
    """
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("empty amount")

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif has_comma:
        cleaned = cleaned.replace(",", ".")

    return Decimal(cleaned)
