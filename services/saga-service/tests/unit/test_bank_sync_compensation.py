from __future__ import annotations

import pytest

from app.application.orchestrator import SagaOrchestrator, SagaRegistry
from app.application.sagas.bank_sync_saga import BankSyncSagaDefinition
from app.domain.entities import SagaStatus, StepStatus
from tests.unit.test_orchestrator import InMemoryUnitOfWork


@pytest.fixture
def bank_sync_uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


@pytest.fixture
def bank_sync_orchestrator(bank_sync_uow: InMemoryUnitOfWork) -> SagaOrchestrator:
    registry = SagaRegistry()
    registry.register(BankSyncSagaDefinition())
    return SagaOrchestrator(bank_sync_uow, registry)


def _bank_sync_context() -> dict:
    return {
        "connection_id": "conn-1",
        "user_id": 1,
        "account_id": 2,
        "account_name": "Main",
        "bank_account_uid": "bank-uid",
    }


@pytest.mark.asyncio
async def test_import_failure_marks_saga_failed_without_rollback(
    bank_sync_orchestrator: SagaOrchestrator,
    bank_sync_uow: InMemoryUnitOfWork,
) -> None:
    saga = await bank_sync_orchestrator.start_saga("bank_sync", _bank_sync_context())

    await bank_sync_orchestrator.handle_reply(
        saga.id,
        "fetch_transactions",
        success=True,
        result_data={"items": [{"amount": "10"}], "total_fetched": 1, "parse_skipped": 0},
    )

    result = await bank_sync_orchestrator.handle_reply(
        saga.id,
        "import_transactions",
        success=False,
        error_message="bulk import rejected",
    )

    assert result.status == SagaStatus.FAILED
    assert result.error_detail == "bulk import rejected"
    rollback_events = [e for e in bank_sync_uow.outbox.events if e["event_type"] == "saga.cmd.rollback_import"]
    assert rollback_events == []


@pytest.mark.asyncio
async def test_mark_sync_failure_triggers_rollback_import(
    bank_sync_orchestrator: SagaOrchestrator,
    bank_sync_uow: InMemoryUnitOfWork,
) -> None:
    saga = await bank_sync_orchestrator.start_saga("bank_sync", _bank_sync_context())

    await bank_sync_orchestrator.handle_reply(
        saga.id,
        "fetch_transactions",
        success=True,
        result_data={"items": [{"amount": "10"}], "total_fetched": 1, "parse_skipped": 0},
    )
    await bank_sync_orchestrator.handle_reply(
        saga.id,
        "import_transactions",
        success=True,
        result_data={"imported": 2, "duplicates_skipped": 0, "errors": 0, "imported_ids": [501, 502]},
    )

    result = await bank_sync_orchestrator.handle_reply(
        saga.id,
        "mark_sync_complete",
        success=False,
        error_message="banking DB unavailable",
    )

    assert result.status == SagaStatus.COMPENSATING
    rollback_events = [e for e in bank_sync_uow.outbox.events if e["event_type"] == "saga.cmd.rollback_import"]
    assert len(rollback_events) == 1
    assert rollback_events[0]["payload"]["transaction_ids"] == [501, 502]
    assert rollback_events[0]["payload"]["user_id"] == 1
    assert rollback_events[0]["payload"]["step_name"] == "import_transactions"


@pytest.mark.asyncio
async def test_compensation_reply_marks_saga_failed_after_rollback(bank_sync_orchestrator: SagaOrchestrator) -> None:
    saga = await bank_sync_orchestrator.start_saga("bank_sync", _bank_sync_context())

    await bank_sync_orchestrator.handle_reply(
        saga.id,
        "fetch_transactions",
        success=True,
        result_data={"items": [], "total_fetched": 0, "parse_skipped": 0},
    )
    await bank_sync_orchestrator.handle_reply(
        saga.id,
        "import_transactions",
        success=True,
        result_data={"imported": 1, "duplicates_skipped": 0, "errors": 0, "imported_ids": [777]},
    )
    await bank_sync_orchestrator.handle_reply(
        saga.id,
        "mark_sync_complete",
        success=False,
        error_message="downstream failed",
    )

    result = await bank_sync_orchestrator.handle_compensation_reply(saga.id, "import_transactions")

    assert result.status == SagaStatus.FAILED
    assert result.completed_at is not None
    assert result.steps[1].status == StepStatus.COMPENSATED
    assert result.error_detail == "downstream failed"
