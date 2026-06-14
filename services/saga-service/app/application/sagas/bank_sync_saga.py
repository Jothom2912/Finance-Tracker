from __future__ import annotations

from typing import Any

from app.domain.saga_definition import SagaDefinition, StepDefinition


class BankSyncSagaDefinition(SagaDefinition):
    """Bank sync saga: fetch → import → mark complete.

    Steps:
      0. fetch_transactions — banking-service fetches from Enable Banking API
      1. import_transactions — transaction-service bulk imports
      2. mark_sync_complete — banking-service updates last_synced_at
    """

    @property
    def saga_type(self) -> str:
        return "bank_sync"

    @property
    def steps(self) -> list[StepDefinition]:
        return [
            StepDefinition(
                name="fetch_transactions",
                command_event_type="saga.cmd.bank_fetch_transactions",
                compensate_event_type=None,
            ),
            StepDefinition(
                name="import_transactions",
                command_event_type="saga.cmd.bulk_import_transactions",
                compensate_event_type="saga.cmd.rollback_import",
            ),
            StepDefinition(
                name="mark_sync_complete",
                command_event_type="saga.cmd.mark_sync_complete",
                compensate_event_type=None,
            ),
        ]

    def build_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any]:
        if step_index == 0:
            return {
                "connection_id": context["connection_id"],
                "user_id": context["user_id"],
                "date_from": context.get("date_from"),
                "bank_account_uid": context["bank_account_uid"],
            }
        elif step_index == 1:
            return {
                "user_id": context["user_id"],
                "account_id": context["account_id"],
                "account_name": context["account_name"],
                "items": context["fetched_items"],
            }
        elif step_index == 2:
            return {
                "connection_id": context["connection_id"],
                "user_id": context["user_id"],
                "total_fetched": context.get("total_fetched", 0),
                "new_imported": context.get("new_imported", 0),
                "duplicates_skipped": context.get("duplicates_skipped", 0),
                "errors": context.get("errors", 0),
            }
        return {}

    def build_compensate_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any] | None:
        if step_index == 1:
            imported_ids = context.get("imported_ids", [])
            if not imported_ids:
                return None
            return {
                "user_id": context["user_id"],
                "transaction_ids": imported_ids,
            }
        return None

    def on_reply(self, step_index: int, context: dict[str, Any], result_data: dict[str, Any] | None) -> dict[str, Any]:
        if result_data is None:
            return context

        if step_index == 0:
            context["fetched_items"] = result_data.get("items", [])
            context["total_fetched"] = result_data.get("total_fetched", 0)
            context["parse_skipped"] = result_data.get("parse_skipped", 0)
        elif step_index == 1:
            context["imported_ids"] = result_data.get("imported_ids", [])
            context["new_imported"] = result_data.get("imported", 0)
            context["duplicates_skipped"] = result_data.get("duplicates_skipped", 0)
            context["errors"] = context.get("errors", 0) + result_data.get("errors", 0)

        return context
