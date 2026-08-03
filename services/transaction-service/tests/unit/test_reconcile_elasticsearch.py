from decimal import Decimal

import pytest
from app.maintenance.reconcile_elasticsearch import TransactionFact, reconcile


def _fact(transaction_id: int, *, amount: str = "10.00", category_id: int | None = 1) -> TransactionFact:
    return TransactionFact(
        transaction_id=transaction_id,
        user_id=7,
        account_id=8,
        category_id=category_id,
        tx_date="2026-08-01",
        amount=Decimal(amount),
    )


def test_reconciliation_is_exact_and_deterministic() -> None:
    rows = [_fact(2, amount="-2.25"), _fact(1, amount="10.00")]
    first = reconcile(rows, list(reversed(rows)))
    second = reconcile(rows, list(reversed(rows)))
    assert first == second
    assert first["reconciled"] is True
    assert first["postgres_count"] == first["elasticsearch_count"] == 2
    assert first["postgres_hash"] == first["elasticsearch_hash"]


def test_equal_counts_do_not_hide_id_or_amount_drift() -> None:
    report = reconcile([_fact(1), _fact(2)], [_fact(1, amount="10.01"), _fact(3)])
    assert report["reconciled"] is False
    assert report["missing_in_elasticsearch"] == [2]
    assert report["extra_in_elasticsearch"] == [3]
    assert report["field_mismatches"][0]["transaction_id"] == 1
    assert report["group_mismatches"]["global"]["postgres"]["amount"] == "20.00"
    assert report["group_mismatches"]["global"]["elasticsearch"]["amount"] == "20.01"


def test_duplicate_ids_fail_closed() -> None:
    with pytest.raises(ValueError, match="duplicate transaction_id 1"):
        reconcile([_fact(1)], [_fact(1), _fact(1)])
