from __future__ import annotations

from app.workers.saga_start_consumer import SagaStartConsumer


def test_parse_bank_sync_start_event_from_flat_payload() -> None:
    body = {
        "event_type": "saga.bank_sync.start",
        "saga_type": "bank_sync",
        "correlation_id": "saga-123",
        "connection_id": "conn-1",
        "user_id": 42,
        "account_id": 7,
        "account_name": "Main",
        "bank_account_uid": "uid-abc",
        "date_from": "2026-01-01",
    }

    saga_type, context, correlation_id = SagaStartConsumer._parse_start_event(body)

    assert saga_type == "bank_sync"
    assert correlation_id == "saga-123"
    assert context["connection_id"] == "conn-1"
    assert context["user_id"] == 42
    assert context["account_id"] == 7
    assert context["account_name"] == "Main"
    assert context["bank_account_uid"] == "uid-abc"
    assert context["date_from"] == "2026-01-01"


def test_parse_generic_start_event_with_nested_context() -> None:
    body = {
        "saga_type": "custom_saga",
        "correlation_id": "corr-1",
        "context": {"foo": "bar"},
    }

    saga_type, context, correlation_id = SagaStartConsumer._parse_start_event(body)

    assert saga_type == "custom_saga"
    assert correlation_id == "corr-1"
    assert context == {"foo": "bar"}
