from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.application.ports.outbound import IUnitOfWork
from app.domain.entities import SagaInstance, SagaStatus, SagaStep, StepStatus
from app.domain.exceptions import (
    DuplicateSaga,
    SagaAlreadyCompleted,
    SagaNotFound,
    SagaStepMismatch,
    UnknownSagaType,
)
from app.domain.saga_definition import SagaDefinition

logger = logging.getLogger(__name__)


class SagaRegistry:
    """Holds all registered saga definitions, keyed by saga_type."""

    def __init__(self) -> None:
        self._definitions: dict[str, SagaDefinition] = {}

    def register(self, definition: SagaDefinition) -> None:
        self._definitions[definition.saga_type] = definition

    def get(self, saga_type: str) -> SagaDefinition:
        defn = self._definitions.get(saga_type)
        if defn is None:
            raise UnknownSagaType(saga_type)
        return defn


class SagaOrchestrator:
    """Generic saga orchestration engine.

    Responsibilities:
    - Start new sagas (create instance + publish first command)
    - Handle replies (advance or compensate)
    - Detect timeouts
    """

    def __init__(self, uow: IUnitOfWork, registry: SagaRegistry) -> None:
        self._uow = uow
        self._registry = registry

    async def start_saga(
        self, saga_type: str, context: dict[str, Any], correlation_id: str | None = None
    ) -> SagaInstance:
        definition = self._registry.get(saga_type)

        saga = SagaInstance(
            saga_type=saga_type,
            status=SagaStatus.STARTED,
            context=context,
            steps=[SagaStep(index=i, name=step_def.name) for i, step_def in enumerate(definition.steps)],
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        if correlation_id:
            saga.id = correlation_id
            saga.correlation_id = correlation_id
        else:
            saga.correlation_id = saga.id

        async with self._uow:
            existing = await self._uow.sagas.get_by_correlation_id(saga.correlation_id)
            if existing is not None:
                raise DuplicateSaga(saga.correlation_id)

            await self._uow.sagas.save(saga)
            await self._publish_step_command(saga, definition, 0)
            saga.steps[0].status = StepStatus.EXECUTING
            saga.steps[0].command_sent_at = datetime.now(timezone.utc)
            await self._uow.sagas.update(saga)
            await self._uow.commit()

        logger.info("Saga started: type=%s id=%s correlation=%s", saga_type, saga.id, saga.correlation_id)
        return saga

    async def handle_reply(
        self,
        saga_id: str,
        step_name: str,
        success: bool,
        result_data: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> SagaInstance:
        async with self._uow:
            # Row lock held across read→decide→write (released at commit or
            # rollback): concurrent replies/timeout marking serialize here.
            saga = await self._uow.sagas.get_by_id(saga_id, for_update=True)
            if saga is None:
                raise SagaNotFound(saga_id)
            if saga.status != SagaStatus.STARTED:
                # Terminal, or already compensating (e.g. timed out while this
                # reply was in flight): treat the late reply as a duplicate so
                # the consumer acks instead of dead-lettering.
                raise SagaAlreadyCompleted(saga_id)

            definition = self._registry.get(saga.saga_type)
            current_step = saga.current_step_obj
            if current_step is None or current_step.name != step_name:
                expected = current_step.name if current_step else "<none>"
                raise SagaStepMismatch(saga_id, expected, step_name)

            current_step.reply_received_at = datetime.now(timezone.utc)
            saga.updated_at = datetime.now(timezone.utc)

            if success:
                await self._advance(saga, definition, result_data)
            else:
                await self._begin_compensation(saga, definition, error_message)

            await self._uow.sagas.update(saga)
            await self._uow.commit()

        return saga

    async def handle_compensation_reply(
        self,
        saga_id: str,
        step_name: str,
        success: bool,
        error_message: str | None = None,
    ) -> SagaInstance:
        async with self._uow:
            # Row lock held across read→decide→write (see handle_reply).
            saga = await self._uow.sagas.get_by_id(saga_id, for_update=True)
            if saga is None:
                raise SagaNotFound(saga_id)
            if saga.status != SagaStatus.COMPENSATING:
                raise SagaAlreadyCompleted(saga_id)

            definition = self._registry.get(saga.saga_type)
            current_step = saga.current_step_obj
            if current_step is None or current_step.name != step_name:
                expected = current_step.name if current_step else "<none>"
                raise SagaStepMismatch(saga_id, expected, step_name)

            saga.updated_at = datetime.now(timezone.utc)

            if success:
                current_step.compensated_at = datetime.now(timezone.utc)
                current_step.status = StepStatus.COMPENSATED
                await self._compensate_previous(saga, definition)
            else:
                current_step.status = StepStatus.FAILED
                current_step.error_detail = error_message
                saga.status = SagaStatus.FAILED
                saga.error_detail = f"compensation failed: {step_name}" + (
                    f": {error_message}" if error_message else ""
                )
                saga.completed_at = datetime.now(timezone.utc)
                logger.error("Saga compensation failed: id=%s step=%s error=%s", saga.id, step_name, error_message)

            await self._uow.sagas.update(saga)
            await self._uow.commit()

        return saga

    # Marker recorded in error_detail after a stale compensation command has
    # been re-emitted once; a second stale detection then fails the saga.
    _COMPENSATION_REEMIT_MARKER = "compensation command re-emitted"

    async def check_timeouts(self, max_age: timedelta) -> list[SagaInstance]:
        cutoff = datetime.now(timezone.utc) - max_age
        async with self._uow:
            # Cheap unlocked scan: ids only. Every candidate is then re-loaded
            # under a row lock and re-validated, because a reply may win the
            # race between the scan and the lock acquisition.
            stale_ids = await self._uow.sagas.find_stale_ids(older_than=cutoff)
            handled: list[SagaInstance] = []
            for saga_id in stale_ids:
                saga = await self._uow.sagas.get_by_id(saga_id, for_update=True)
                if saga is None or not saga.is_active or not self._is_stale(saga, cutoff):
                    # A concurrent reply advanced or completed the saga after
                    # the scan — never resurrect or overwrite it.
                    continue

                definition = self._registry.get(saga.saga_type)
                if saga.status == SagaStatus.COMPENSATING:
                    await self._handle_stale_compensation(saga, definition, max_age)
                else:
                    await self._handle_stale_execution(saga, definition, max_age)

                saga.updated_at = datetime.now(timezone.utc)
                await self._uow.sagas.update(saga)
                handled.append(saga)
            if handled:
                await self._uow.commit()
        return handled

    @staticmethod
    def _is_stale(saga: SagaInstance, cutoff: datetime) -> bool:
        if saga.updated_at is None:
            return True
        updated_at = saga.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return updated_at <= cutoff

    async def _handle_stale_execution(
        self, saga: SagaInstance, definition: SagaDefinition, max_age: timedelta
    ) -> None:
        """A saga stuck in STARTED timed out: compensate if there is anything
        to undo, otherwise mark it timed_out as before."""
        timeout_seconds = max_age.total_seconds()
        if self._has_compensatable_work(saga, definition):
            reason = f"timed out after {timeout_seconds}s; compensating"
            await self._begin_compensation(saga, definition, reason)
            logger.warning("Saga timed out, compensating: id=%s type=%s", saga.id, saga.saga_type)
        else:
            saga.status = SagaStatus.TIMED_OUT
            saga.error_detail = f"Timed out after {timeout_seconds}s"
            saga.completed_at = datetime.now(timezone.utc)
            logger.warning("Saga timed out: id=%s type=%s", saga.id, saga.saga_type)

    async def _handle_stale_compensation(
        self, saga: SagaInstance, definition: SagaDefinition, max_age: timedelta
    ) -> None:
        """A saga stuck in COMPENSATING timed out.

        First detection: re-emit the pending compensation command once via the
        outbox (participants handle it idempotently). Second detection (or no
        re-emittable command): mark the saga FAILED with an explicit reason —
        never TIMED_OUT, never silently resurrected.
        """
        step = saga.current_step_obj
        step_def = definition.steps[saga.current_step] if step is not None else None
        already_reemitted = bool(saga.error_detail and self._COMPENSATION_REEMIT_MARKER in saga.error_detail)

        payload: dict[str, Any] | None = None
        if step is not None and step_def is not None and step_def.compensate_event_type is not None:
            payload = definition.build_compensate_command(saga.current_step, saga.context)

        if already_reemitted or payload is None or step is None or step_def is None:
            if step is not None:
                step.status = StepStatus.FAILED
                step.error_detail = "compensation timed out"
            saga.status = SagaStatus.FAILED
            saga.error_detail = (
                f"{saga.error_detail}; compensation timed out" if saga.error_detail else "compensation timed out"
            )
            saga.completed_at = datetime.now(timezone.utc)
            logger.error(
                "Saga compensation timed out: id=%s step=%s", saga.id, step.name if step else "<none>"
            )
            return

        assert step_def.compensate_event_type is not None
        await self._outbox_compensation_command(saga, step, step_def.compensate_event_type, payload)
        note = f"{self._COMPENSATION_REEMIT_MARKER} after {max_age.total_seconds()}s"
        saga.error_detail = f"{saga.error_detail}; {note}" if saga.error_detail else note
        logger.warning(
            "Saga compensation stale, re-emitting compensation command: id=%s step=%s", saga.id, step.name
        )

    def _has_compensatable_work(self, saga: SagaInstance, definition: SagaDefinition) -> bool:
        for step in saga.steps:
            if step.status != StepStatus.SUCCEEDED:
                continue
            step_def = definition.steps[step.index]
            if step_def.compensate_event_type is None:
                continue
            if definition.build_compensate_command(step.index, saga.context) is not None:
                return True
        return False

    async def _advance(
        self, saga: SagaInstance, definition: SagaDefinition, result_data: dict[str, Any] | None
    ) -> None:
        current_step = saga.steps[saga.current_step]
        current_step.status = StepStatus.SUCCEEDED

        saga.context = definition.on_reply(saga.current_step, saga.context, result_data)

        if saga.is_last_step:
            saga.status = SagaStatus.COMPLETED
            saga.completed_at = datetime.now(timezone.utc)
            logger.info("Saga completed: id=%s type=%s", saga.id, saga.saga_type)
        else:
            saga.current_step += 1
            next_step = saga.steps[saga.current_step]
            next_step.status = StepStatus.EXECUTING
            next_step.command_sent_at = datetime.now(timezone.utc)
            await self._publish_step_command(saga, definition, saga.current_step)

    async def _begin_compensation(
        self, saga: SagaInstance, definition: SagaDefinition, error_message: str | None
    ) -> None:
        current_step = saga.steps[saga.current_step]
        current_step.status = StepStatus.FAILED
        current_step.error_detail = error_message

        saga.status = SagaStatus.COMPENSATING
        saga.error_detail = error_message
        logger.info("Saga entering compensation: id=%s step=%s error=%s", saga.id, current_step.name, error_message)

        await self._compensate_previous(saga, definition)

    async def _compensate_previous(self, saga: SagaInstance, definition: SagaDefinition) -> None:
        while saga.current_step > 0:
            saga.current_step -= 1
            step = saga.steps[saga.current_step]
            if step.status != StepStatus.SUCCEEDED:
                continue

            step_def = definition.steps[saga.current_step]
            if step_def.compensate_event_type is None:
                step.status = StepStatus.COMPENSATED
                step.compensated_at = datetime.now(timezone.utc)
                continue

            payload = definition.build_compensate_command(saga.current_step, saga.context)
            if payload is None:
                step.status = StepStatus.COMPENSATED
                step.compensated_at = datetime.now(timezone.utc)
                continue

            await self._outbox_compensation_command(saga, step, step_def.compensate_event_type, payload)
            return

        saga.status = SagaStatus.FAILED
        saga.completed_at = datetime.now(timezone.utc)
        logger.info("Saga compensation complete (failed): id=%s", saga.id)

    async def _outbox_compensation_command(
        self, saga: SagaInstance, step: SagaStep, compensate_event_type: str, payload: dict[str, Any]
    ) -> None:
        payload["saga_id"] = saga.id
        payload["saga_type"] = saga.saga_type
        payload["step_name"] = step.name
        payload["event_type"] = compensate_event_type
        await self._uow.outbox.add(
            event_type=compensate_event_type,
            payload_json=json.dumps(payload, default=str),
            aggregate_type="saga",
            aggregate_id=saga.id,
            correlation_id=saga.correlation_id,
        )

    async def _publish_step_command(self, saga: SagaInstance, definition: SagaDefinition, step_index: int) -> None:
        step_def = definition.steps[step_index]
        payload = definition.build_command(step_index, saga.context)
        payload["saga_id"] = saga.id
        payload["saga_type"] = saga.saga_type
        payload["step_name"] = step_def.name
        payload["event_type"] = step_def.command_event_type

        await self._uow.outbox.add(
            event_type=step_def.command_event_type,
            payload_json=json.dumps(payload, default=str),
            aggregate_type="saga",
            aggregate_id=saga.id,
            correlation_id=saga.correlation_id,
        )
