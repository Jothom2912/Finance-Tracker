from __future__ import annotations

from app.application.orchestrator import SagaRegistry


def get_saga_registry() -> SagaRegistry:
    from app.application.sagas.bank_sync_saga import BankSyncSagaDefinition

    registry = SagaRegistry()
    registry.register(BankSyncSagaDefinition())
    return registry
