"""Unit tests for ``BankingSagaCommandConsumer._handle_fetch_transactions``.

First coverage of the saga item contract (P2-09): until now nothing
locked the shape of the item dicts banking hands to the saga — the
audit's H10 (entry_reference/currency silently dropped) lived exactly
in that gap.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from app.adapters.outbound.enable_banking_client import BankTransaction
from app.workers.saga_command_consumer import BankingSagaCommandConsumer


def _bank_txn(**overrides) -> BankTransaction:  # type: ignore[no-untyped-def]
    defaults = {
        "transaction_id": "EB-REF-1",
        "amount": Decimal("-49.99"),
        "currency": "DKK",
        "description": "Netto",
        "date": date(2026, 3, 1),
    }
    defaults.update(overrides)
    return BankTransaction(**defaults)


async def _fetch_items(transactions: list[BankTransaction]) -> list[dict]:
    consumer = BankingSagaCommandConsumer()
    client = AsyncMock()
    client.get_transactions.return_value = (transactions, 0)
    consumer._banking_client = client

    with patch.object(consumer, "_reject_if_consent_expired", AsyncMock(return_value=None)):
        reply = await consumer._handle_fetch_transactions(
            {"connection_id": str(uuid4()), "bank_account_uid": "acc-1"},
        )

    assert reply["success"] is True
    return reply["result_data"]["items"]


@pytest.mark.asyncio
async def test_items_carry_external_id_and_currency() -> None:
    items = await _fetch_items(
        [
            _bank_txn(transaction_id="EB-REF-1", currency="DKK"),
            _bank_txn(transaction_id="EB-REF-2", currency="EUR", amount=Decimal("100.00")),
        ],
    )

    assert [i["external_id"] for i in items] == ["EB-REF-1", "EB-REF-2"]
    assert [i["currency"] for i in items] == ["DKK", "EUR"]


@pytest.mark.asyncio
async def test_blank_transaction_id_maps_to_none_external_id() -> None:
    """""/whitespace entry_references must never reach transaction-service
    as dedup keys — normalize to None so it falls back to the fuzzy key."""
    items = await _fetch_items(
        [_bank_txn(transaction_id=""), _bank_txn(transaction_id="   ")],
    )

    assert [i["external_id"] for i in items] == [None, None]


@pytest.mark.asyncio
async def test_missing_currency_defaults_to_dkk() -> None:
    items = await _fetch_items([_bank_txn(currency="")])

    assert items[0]["currency"] == "DKK"


@pytest.mark.asyncio
async def test_existing_mapping_contract_unchanged() -> None:
    """Locks the pre-P2-09 item fields: abs amount as string, sign folded
    into transaction_type, ISO date, description verbatim."""
    items = await _fetch_items(
        [
            _bank_txn(amount=Decimal("-49.99"), description="Netto"),
            _bank_txn(transaction_id="EB-REF-2", amount=Decimal("15000.00"), description="Løn"),
        ],
    )

    assert items[0]["amount"] == "49.99"
    assert items[0]["transaction_type"] == "expense"
    assert items[0]["date"] == "2026-03-01"
    assert items[0]["description"] == "Netto"
    assert items[1]["amount"] == "15000.00"
    assert items[1]["transaction_type"] == "income"
