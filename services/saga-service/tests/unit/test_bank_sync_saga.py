from __future__ import annotations

from app.application.sagas.bank_sync_saga import BankSyncSagaDefinition


def test_build_compensate_command_returns_rollback_when_imported_ids_present() -> None:
    definition = BankSyncSagaDefinition()
    context = {"user_id": 42, "imported_ids": [101, 102]}

    payload = definition.build_compensate_command(1, context)

    assert payload == {"user_id": 42, "transaction_ids": [101, 102]}


def test_build_compensate_command_returns_none_when_nothing_imported() -> None:
    definition = BankSyncSagaDefinition()

    assert definition.build_compensate_command(1, {"user_id": 42, "imported_ids": []}) is None
    assert definition.build_compensate_command(1, {"user_id": 42}) is None


def test_on_reply_merges_import_result_into_context() -> None:
    definition = BankSyncSagaDefinition()
    context = {
        "connection_id": "conn-1",
        "user_id": 1,
        "fetched_items": [{"amount": "10"}],
        "total_fetched": 1,
    }

    updated = definition.on_reply(
        1,
        context,
        {
            "imported": 2,
            "duplicates_skipped": 3,
            "errors": 0,
            "imported_ids": [10, 11],
        },
    )

    assert updated["imported_ids"] == [10, 11]
    assert updated["new_imported"] == 2
    assert updated["duplicates_skipped"] == 3
    assert updated["total_fetched"] == 1
