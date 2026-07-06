"""Kanoniske klassifikationsregler for transaktioner.

Dette modul er den autoritative definition af hvornår en transaktion
tæller som indtægt/udgift i analytics read-siden (jf. ADR-004). Reglen
matcher gateway-servicens historiske adfærd: ``transaction_type`` er det
primære signal, med fortegns-fallback for legacy-rækker uden type.
"""

from __future__ import annotations

from typing import Any


def normalize_tx_type(raw_value: Any) -> str:
    if raw_value is None:
        return ""
    if hasattr(raw_value, "value"):
        return str(raw_value.value).lower()
    return str(raw_value).lower()


def is_income(tx_type: str, amount: float) -> bool:
    return tx_type == "income" or (tx_type == "" and amount > 0)


def is_expense(tx_type: str, amount: float) -> bool:
    return tx_type == "expense" or (tx_type == "" and amount < 0)
