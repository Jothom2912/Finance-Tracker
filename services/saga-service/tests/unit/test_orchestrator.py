from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from app.application.orchestrator import SagaOrchestrator, SagaRegistry
from app.application.ports.outbound import IOutboxRepository, ISagaRepository, IUnitOfWork
from app.domain.entities import SagaInstance, SagaStatus, StepStatus
from app.domain.exceptions import DuplicateSaga, SagaAlreadyCompleted, SagaNotFound, SagaStepMismatch
from app.domain.saga_definition import SagaDefinition, StepDefinition

# ── Test Saga Definition ──────────────────────────────────────────


class TwoStepTestSaga(SagaDefinition):
    @property
    def saga_type(self) -> str:
        return "test_saga"

    @property
    def steps(self) -> list[StepDefinition]:
        return [
            StepDefinition(name="step_one", command_event_type="cmd.step_one", compensate_event_type=None),
            StepDefinition(
                name="step_two", command_event_type="cmd.step_two", compensate_event_type="cmd.undo_step_two"
            ),
        ]

    def build_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any]:
        return {"action": f"do_step_{step_index}", "data": context.get("input")}

    def build_compensate_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any] | None:
        if step_index == 1:
            return {"action": "undo_step_1", "ids": context.get("created_ids", [])}
        return None


class ThreeStepCompensationSaga(SagaDefinition):
    @property
    def saga_type(self) -> str:
        return "three_step"

    @property
    def steps(self) -> list[StepDefinition]:
        return [
            StepDefinition(name="fetch", command_event_type="cmd.fetch", compensate_event_type=None),
            StepDefinition(name="import_data", command_event_type="cmd.import", compensate_event_type="cmd.rollback"),
            StepDefinition(name="complete", command_event_type="cmd.complete", compensate_event_type=None),
        ]

    def build_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any]:
        return {"step": step_index, "context_keys": list(context.keys())}

    def build_compensate_command(self, step_index: int, context: dict[str, Any]) -> dict[str, Any] | None:
        if step_index == 1:
            return {"ids": context.get("imported_ids", [])}
        return None

    def on_reply(self, step_index: int, context: dict[str, Any], result_data: dict[str, Any] | None) -> dict[str, Any]:
        if result_data:
            if step_index == 0:
                context["items"] = result_data.get("items", [])
            elif step_index == 1:
                context["imported_ids"] = result_data.get("ids", [])
        return context


# ── In-Memory Implementations ─────────────────────────────────────


class InMemorySagaRepository(ISagaRepository):
    def __init__(self) -> None:
        self._store: dict[str, SagaInstance] = {}
        # Records (saga_id, for_update) for every get_by_id call so tests can
        # assert that read-modify-write paths take the row lock.
        self.get_by_id_calls: list[tuple[str, bool]] = []

    async def save(self, saga: SagaInstance) -> None:
        self._store[saga.id] = saga

    async def get_by_id(self, saga_id: str, *, for_update: bool = False) -> SagaInstance | None:
        self.get_by_id_calls.append((saga_id, for_update))
        return self._store.get(saga_id)

    async def get_by_correlation_id(self, correlation_id: str) -> SagaInstance | None:
        for saga in self._store.values():
            if saga.correlation_id == correlation_id:
                return saga
        return None

    async def find_stale_ids(self, older_than: datetime) -> list[str]:
        return [
            s.id
            for s in self._store.values()
            if s.is_active and s.updated_at is not None and s.updated_at <= older_than
        ]

    async def update(self, saga: SagaInstance) -> None:
        self._store[saga.id] = saga


class InMemoryOutboxRepository(IOutboxRepository):
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def add(
        self,
        event_type: str,
        payload_json: str,
        aggregate_type: str,
        aggregate_id: str,
        correlation_id: str | None = None,
    ) -> None:
        self.events.append(
            {
                "event_type": event_type,
                "payload": json.loads(payload_json),
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "correlation_id": correlation_id,
            }
        )


class InMemoryUnitOfWork(IUnitOfWork):
    def __init__(self) -> None:
        self.sagas = InMemorySagaRepository()
        self.outbox = InMemoryOutboxRepository()
        self.committed = False

    async def __aenter__(self) -> "InMemoryUnitOfWork":
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def registry() -> SagaRegistry:
    reg = SagaRegistry()
    reg.register(TwoStepTestSaga())
    reg.register(ThreeStepCompensationSaga())
    return reg


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


@pytest.fixture
def orchestrator(uow: InMemoryUnitOfWork, registry: SagaRegistry) -> SagaOrchestrator:
    return SagaOrchestrator(uow, registry)


# ── Happy Path Tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_saga_uses_correlation_id_as_saga_id(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "hello"}, correlation_id="fixed-id")

    assert saga.id == "fixed-id"
    assert saga.correlation_id == "fixed-id"


@pytest.mark.asyncio
async def test_start_saga_creates_instance_and_publishes_first_command(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "hello"})

    assert saga.status == SagaStatus.STARTED
    assert saga.current_step == 0
    assert saga.steps[0].status == StepStatus.EXECUTING
    assert len(saga.steps) == 2
    assert uow.committed is True

    assert len(uow.outbox.events) == 1
    event = uow.outbox.events[0]
    assert event["event_type"] == "cmd.step_one"
    assert event["payload"]["action"] == "do_step_0"


@pytest.mark.asyncio
async def test_handle_reply_advances_to_next_step(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    uow.committed = False

    result = await orchestrator.handle_reply(saga.id, "step_one", success=True, result_data={"key": "value"})

    assert result.current_step == 1
    assert result.steps[0].status == StepStatus.SUCCEEDED
    assert result.steps[1].status == StepStatus.EXECUTING
    assert result.status == SagaStatus.STARTED

    assert len(uow.outbox.events) == 2
    assert uow.outbox.events[1]["event_type"] == "cmd.step_two"


@pytest.mark.asyncio
async def test_handle_reply_completes_saga_on_last_step(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    await orchestrator.handle_reply(saga.id, "step_one", success=True)

    result = await orchestrator.handle_reply(saga.id, "step_two", success=True)

    assert result.status == SagaStatus.COMPLETED
    assert result.completed_at is not None
    assert result.steps[1].status == StepStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_three_step_saga_happy_path(orchestrator, uow):
    saga = await orchestrator.start_saga("three_step", {"connection_id": "abc"})

    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": [1, 2, 3]})
    assert saga.context["items"] == [1, 2, 3]

    await orchestrator.handle_reply(saga.id, "import_data", success=True, result_data={"ids": [10, 11]})
    assert saga.context["imported_ids"] == [10, 11]

    result = await orchestrator.handle_reply(saga.id, "complete", success=True)
    assert result.status == SagaStatus.COMPLETED


# ── Failure + Compensation Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_failure_triggers_compensation(orchestrator, uow):
    saga = await orchestrator.start_saga("three_step", {"connection_id": "abc"})
    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": [1]})
    await orchestrator.handle_reply(saga.id, "import_data", success=True, result_data={"ids": [100, 101]})

    result = await orchestrator.handle_reply(saga.id, "complete", success=False, error_message="downstream failed")

    assert result.status == SagaStatus.COMPENSATING or result.status == SagaStatus.FAILED
    compensation_events = [e for e in uow.outbox.events if e["event_type"] == "cmd.rollback"]
    assert len(compensation_events) == 1
    assert compensation_events[0]["payload"]["ids"] == [100, 101]


@pytest.mark.asyncio
async def test_failure_at_first_step_no_compensation_needed(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})

    result = await orchestrator.handle_reply(saga.id, "step_one", success=False, error_message="oops")

    assert result.status == SagaStatus.FAILED
    assert result.error_detail == "oops"
    compensation_events = [e for e in uow.outbox.events if "undo" in e["event_type"]]
    assert len(compensation_events) == 0


@pytest.mark.asyncio
async def test_failure_with_compensation_on_step_two(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    await orchestrator.handle_reply(saga.id, "step_one", success=True)

    result = await orchestrator.handle_reply(saga.id, "step_two", success=False, error_message="import failed")

    assert result.status == SagaStatus.FAILED
    assert result.error_detail == "import failed"


# ── Timeout Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_check_timeouts_marks_stale_sagas(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    saga.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await uow.sagas.update(saga)

    timed_out = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    assert len(timed_out) == 1
    assert timed_out[0].id == saga.id
    assert timed_out[0].status == SagaStatus.TIMED_OUT
    assert timed_out[0].completed_at is not None


@pytest.mark.asyncio
async def test_check_timeouts_ignores_completed_sagas(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    await orchestrator.handle_reply(saga.id, "step_one", success=True)
    await orchestrator.handle_reply(saga.id, "step_two", success=True)

    saga.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await uow.sagas.update(saga)

    timed_out = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))
    assert len(timed_out) == 0


@pytest.mark.asyncio
async def test_check_timeouts_ignores_recent_sagas(orchestrator, uow):
    await orchestrator.start_saga("test_saga", {"input": "data"})

    timed_out = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))
    assert len(timed_out) == 0


def _make_stale(saga: SagaInstance, minutes: int = 10) -> None:
    saga.updated_at = datetime.now(timezone.utc) - timedelta(minutes=minutes)


@pytest.mark.asyncio
async def test_timeout_with_compensatable_step_begins_compensation(orchestrator, uow):
    """H7: a stale saga with a succeeded, compensatable step is rolled back
    instead of being abandoned as timed_out."""
    saga = await orchestrator.start_saga("three_step", {"connection_id": "abc"})
    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": [1]})
    await orchestrator.handle_reply(saga.id, "import_data", success=True, result_data={"ids": [100, 101]})
    # Now stuck at step "complete" (executing), with import_data succeeded.
    _make_stale(saga)
    await uow.sagas.update(saga)

    handled = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    assert len(handled) == 1
    result = handled[0]
    assert result.status == SagaStatus.COMPENSATING
    assert result.error_detail == "timed out after 300.0s; compensating"
    assert result.completed_at is None
    assert result.steps[2].status == StepStatus.FAILED  # the stuck step
    rollback_events = [e for e in uow.outbox.events if e["event_type"] == "cmd.rollback"]
    assert len(rollback_events) == 1
    assert rollback_events[0]["payload"]["ids"] == [100, 101]


@pytest.mark.asyncio
async def test_timeout_with_nothing_to_compensate_marks_timed_out(orchestrator, uow):
    """H7: succeeded steps without a compensation command do not prevent the
    terminal timed_out marking."""
    saga = await orchestrator.start_saga("three_step", {"connection_id": "abc"})
    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": [1]})
    # Stuck at import_data; only "fetch" succeeded and it has no compensation.
    _make_stale(saga)
    await uow.sagas.update(saga)

    handled = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    assert len(handled) == 1
    assert handled[0].status == SagaStatus.TIMED_OUT
    assert handled[0].completed_at is not None
    rollback_events = [e for e in uow.outbox.events if e["event_type"] == "cmd.rollback"]
    assert rollback_events == []


@pytest.mark.asyncio
async def test_late_reply_after_timeout_compensation_raises_already_completed(orchestrator, uow):
    """A reply for the stuck step arriving after the timeout routed the saga
    into compensation must ack cleanly (SagaAlreadyCompleted), not resurrect."""
    saga = await orchestrator.start_saga("three_step", {"connection_id": "abc"})
    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": [1]})
    await orchestrator.handle_reply(saga.id, "import_data", success=True, result_data={"ids": [100]})
    _make_stale(saga)
    await uow.sagas.update(saga)
    await orchestrator.check_timeouts(max_age=timedelta(minutes=5))
    assert saga.status == SagaStatus.COMPENSATING

    with pytest.raises(SagaAlreadyCompleted):
        await orchestrator.handle_reply(saga.id, "complete", success=True)

    assert saga.status == SagaStatus.COMPENSATING  # untouched


@pytest.mark.asyncio
async def test_late_reply_after_timed_out_raises_already_completed(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    _make_stale(saga)
    await uow.sagas.update(saga)
    await orchestrator.check_timeouts(max_age=timedelta(minutes=5))
    assert saga.status == SagaStatus.TIMED_OUT

    with pytest.raises(SagaAlreadyCompleted):
        await orchestrator.handle_reply(saga.id, "step_one", success=True)

    assert saga.status == SagaStatus.TIMED_OUT


@pytest.mark.asyncio
async def test_compensation_reply_still_works_after_timeout_compensation(orchestrator, uow):
    """The compensation triggered by a timeout completes normally when the
    participant replies."""
    saga = await orchestrator.start_saga("three_step", {"connection_id": "abc"})
    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": [1]})
    await orchestrator.handle_reply(saga.id, "import_data", success=True, result_data={"ids": [100]})
    _make_stale(saga)
    await uow.sagas.update(saga)
    await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    result = await orchestrator.handle_compensation_reply(saga.id, "import_data", success=True)

    assert result.status == SagaStatus.FAILED
    assert result.steps[1].status == StepStatus.COMPENSATED
    assert result.completed_at is not None


# ── Stuck Compensation Tests (H7 part 2) ──────────────────────────


async def _saga_in_compensating_state(orchestrator, uow) -> SagaInstance:
    saga = await orchestrator.start_saga("three_step", {"connection_id": "abc"})
    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": [1]})
    await orchestrator.handle_reply(saga.id, "import_data", success=True, result_data={"ids": [100]})
    await orchestrator.handle_reply(saga.id, "complete", success=False, error_message="downstream failed")
    assert saga.status == SagaStatus.COMPENSATING
    return saga


@pytest.mark.asyncio
async def test_stuck_compensation_reemits_command_once(orchestrator, uow):
    saga = await _saga_in_compensating_state(orchestrator, uow)
    _make_stale(saga)
    await uow.sagas.update(saga)

    handled = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    assert len(handled) == 1
    assert saga.status == SagaStatus.COMPENSATING  # not killed, not timed_out
    assert saga.completed_at is None
    assert "compensation command re-emitted" in (saga.error_detail or "")
    assert "downstream failed" in (saga.error_detail or "")
    rollback_events = [e for e in uow.outbox.events if e["event_type"] == "cmd.rollback"]
    assert len(rollback_events) == 2  # original + re-emitted
    assert rollback_events[1]["payload"]["ids"] == [100]


@pytest.mark.asyncio
async def test_stuck_compensation_fails_after_reemit_did_not_help(orchestrator, uow):
    saga = await _saga_in_compensating_state(orchestrator, uow)
    _make_stale(saga)
    await uow.sagas.update(saga)
    await orchestrator.check_timeouts(max_age=timedelta(minutes=5))  # first: re-emit
    _make_stale(saga)
    await uow.sagas.update(saga)

    handled = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))  # second: give up

    assert len(handled) == 1
    assert saga.status == SagaStatus.FAILED  # never TIMED_OUT
    assert saga.completed_at is not None
    assert "compensation timed out" in (saga.error_detail or "")
    assert saga.steps[1].status == StepStatus.FAILED
    rollback_events = [e for e in uow.outbox.events if e["event_type"] == "cmd.rollback"]
    assert len(rollback_events) == 2  # no third emission


@pytest.mark.asyncio
async def test_late_compensation_reply_after_compensation_failed_raises_already_completed(orchestrator, uow):
    saga = await _saga_in_compensating_state(orchestrator, uow)
    for _ in range(2):
        _make_stale(saga)
        await uow.sagas.update(saga)
        await orchestrator.check_timeouts(max_age=timedelta(minutes=5))
    assert saga.status == SagaStatus.FAILED

    with pytest.raises(SagaAlreadyCompleted):
        await orchestrator.handle_compensation_reply(saga.id, "import_data", success=True)

    assert saga.status == SagaStatus.FAILED


# ── Locking / Race Tests (H8) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_reply_reads_saga_with_row_lock(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    uow.sagas.get_by_id_calls.clear()

    await orchestrator.handle_reply(saga.id, "step_one", success=True)

    assert uow.sagas.get_by_id_calls == [(saga.id, True)]


@pytest.mark.asyncio
async def test_handle_compensation_reply_reads_saga_with_row_lock(orchestrator, uow):
    saga = await _saga_in_compensating_state(orchestrator, uow)
    uow.sagas.get_by_id_calls.clear()

    await orchestrator.handle_compensation_reply(saga.id, "import_data", success=True)

    assert uow.sagas.get_by_id_calls == [(saga.id, True)]


@pytest.mark.asyncio
async def test_check_timeouts_reads_each_candidate_with_row_lock(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    _make_stale(saga)
    await uow.sagas.update(saga)
    uow.sagas.get_by_id_calls.clear()

    await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    assert uow.sagas.get_by_id_calls == [(saga.id, True)]


@pytest.mark.asyncio
async def test_check_timeouts_skips_saga_completed_between_scan_and_lock(orchestrator, uow):
    """Race: the staleness scan flagged the saga, but a reply completed it
    before the timeout worker acquired the row lock. The locked re-read must
    see the terminal state and never resurrect it."""
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    await orchestrator.handle_reply(saga.id, "step_one", success=True)
    await orchestrator.handle_reply(saga.id, "step_two", success=True)
    assert saga.status == SagaStatus.COMPLETED

    async def stale_scan_snapshot(older_than: datetime) -> list[str]:
        return [saga.id]  # stale snapshot taken before the reply committed

    uow.sagas.find_stale_ids = stale_scan_snapshot  # type: ignore[method-assign]

    handled = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    assert handled == []
    stored = await uow.sagas.get_by_id(saga.id)
    assert stored is not None and stored.status == SagaStatus.COMPLETED


@pytest.mark.asyncio
async def test_check_timeouts_skips_saga_refreshed_between_scan_and_lock(orchestrator, uow):
    """Race: a reply advanced the saga (bumping updated_at) after the scan.
    The locked re-read re-validates staleness and leaves the saga alone."""
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    # updated_at is fresh (just started), but the scan claims it is stale.

    async def stale_scan_snapshot(older_than: datetime) -> list[str]:
        return [saga.id]

    uow.sagas.find_stale_ids = stale_scan_snapshot  # type: ignore[method-assign]

    handled = await orchestrator.check_timeouts(max_age=timedelta(minutes=5))

    assert handled == []
    stored = await uow.sagas.get_by_id(saga.id)
    assert stored is not None and stored.status == SagaStatus.STARTED


# ── Duplicate / Error Handling Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_saga_raises_error(orchestrator, uow):
    await orchestrator.start_saga("test_saga", {"input": "data"}, correlation_id="unique-123")

    with pytest.raises(DuplicateSaga):
        await orchestrator.start_saga("test_saga", {"input": "data2"}, correlation_id="unique-123")


@pytest.mark.asyncio
async def test_reply_to_nonexistent_saga_raises_error(orchestrator, uow):
    with pytest.raises(SagaNotFound):
        await orchestrator.handle_reply("nonexistent-id", "step_one", success=True)


@pytest.mark.asyncio
async def test_reply_to_completed_saga_raises_error(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})
    await orchestrator.handle_reply(saga.id, "step_one", success=True)
    await orchestrator.handle_reply(saga.id, "step_two", success=True)

    with pytest.raises(SagaAlreadyCompleted):
        await orchestrator.handle_reply(saga.id, "step_two", success=True)


@pytest.mark.asyncio
async def test_reply_with_wrong_step_name_raises_error(orchestrator, uow):
    saga = await orchestrator.start_saga("test_saga", {"input": "data"})

    with pytest.raises(SagaStepMismatch):
        await orchestrator.handle_reply(saga.id, "wrong_step", success=True)


@pytest.mark.asyncio
async def test_context_is_preserved_across_steps(orchestrator, uow):
    saga = await orchestrator.start_saga("three_step", {"connection_id": "c1", "user_id": 42})

    await orchestrator.handle_reply(saga.id, "fetch", success=True, result_data={"items": ["tx1", "tx2"]})
    assert saga.context["items"] == ["tx1", "tx2"]
    assert saga.context["connection_id"] == "c1"

    await orchestrator.handle_reply(saga.id, "import_data", success=True, result_data={"ids": [1, 2]})
    assert saga.context["imported_ids"] == [1, 2]
    assert saga.context["items"] == ["tx1", "tx2"]
