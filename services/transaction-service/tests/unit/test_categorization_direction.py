"""TAX-14 — every producer sends the direction, derived from transaction_type.

``amount`` is stored as an unsigned magnitude, so a categorizer that infers
direction from its sign reads every row as incoming. These tests pin what each
call site actually puts on the wire for an expense and an income row, per
producer, because the previous suite only ever asserted the description and the
amount — the two fields that were already right.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.application.dto import (
    BulkCreateTransactionDTO,
    BulkCreateTransactionItemDTO,
    CreateTransactionDTO,
)
from app.domain.entities import TransactionType, direction_of

from tests.unit.test_transaction_service import _build_service, _make_transaction


class TestDirectionOf:
    def test_expense_is_outgoing_and_income_is_incoming(self) -> None:
        assert direction_of(TransactionType.EXPENSE) == "outgoing"
        assert direction_of(TransactionType.INCOME) == "incoming"

    def test_accepts_the_string_form_the_event_payload_carries(self) -> None:
        assert direction_of("expense") == "outgoing"
        assert direction_of("income") == "incoming"

    @pytest.mark.parametrize("bad", ["", None, "transfer", "outgoing"])
    def test_unknown_type_raises_instead_of_defaulting(self, bad: str | None) -> None:
        with pytest.raises(ValueError, match="cannot derive categorization direction"):
            direction_of(bad)


def _cat_client() -> AsyncMock:
    client = AsyncMock()
    client.categorize.return_value = MagicMock(category_id=1, subcategory_id=3, tier="rule", confidence="high")
    client.categorize_batch.return_value = []
    return client


class TestSyncCreateProducer:
    @pytest.mark.asyncio()
    @pytest.mark.parametrize(
        ("transaction_type", "expected"),
        [(TransactionType.EXPENSE, "outgoing"), (TransactionType.INCOME, "incoming")],
    )
    async def test_sends_the_direction_for_the_transaction_type(
        self, transaction_type: TransactionType, expected: str
    ) -> None:
        service, uow = _build_service()
        service._cat_client = _cat_client()
        uow.transactions.create.return_value = _make_transaction()
        dto = CreateTransactionDTO(
            account_id=100,
            account_name="Main Account",
            # Positive, as this service stores it — the sign carries no direction.
            amount=Decimal("299.00"),
            transaction_type=transaction_type,
            description="MobilePay Telenor 24836308437046",
            date=date(2026, 8, 3),
        )

        await service.create_transaction(user_id=10, dto=dto)

        kwargs = service._cat_client.categorize.call_args.kwargs
        assert kwargs["direction"] == expected
        assert kwargs["amount"] == 299.00


class TestBulkImportProducer:
    @pytest.mark.asyncio()
    async def test_sends_a_direction_per_item(self) -> None:
        service, uow = _build_service()
        service._cat_client = _cat_client()
        uow.transactions.find_existing_dedup_keys.return_value = set()
        uow.transactions.bulk_create.return_value = [_make_transaction(id=1), _make_transaction(id=2)]
        dto = BulkCreateTransactionDTO(
            items=[
                BulkCreateTransactionItemDTO(
                    account_id=100,
                    account_name="Main Account",
                    amount=Decimal("41.09"),
                    transaction_type=TransactionType.EXPENSE,
                    description="NETTO 7760",
                    date=date(2026, 8, 3),
                ),
                BulkCreateTransactionItemDTO(
                    account_id=100,
                    account_name="Main Account",
                    amount=Decimal("820.00"),
                    transaction_type=TransactionType.INCOME,
                    description="Boligstøtte",
                    date=date(2026, 8, 3),
                ),
            ]
        )

        await service.bulk_import(user_id=10, dto=dto)

        items = service._cat_client.categorize_batch.call_args.args[0]
        assert [item["direction"] for item in items] == ["outgoing", "incoming"]
        assert [item["amount"] for item in items] == [41.09, 820.00]
