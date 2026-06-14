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
            saga = await self._uow.sagas.get_by_id(saga_id)
            if saga is None:
                raise SagaNotFound(saga_id)
            if not saga.is_active:
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
    ) -> SagaInstance:
        async with self._uow:
            saga = await self._uow.sagas.get_by_id(saga_id)
            if saga is None:
                raise SagaNotFound(saga_id)
            if saga.status != SagaStatus.COMPENSATING:
                raise SagaAlreadyCompleted(saga_id)

            definition = self._registry.get(saga.saga_type)
            current_step = saga.current_step_obj
            if current_step is not None:
                current_step.compensated_at = datetime.now(timezone.utc)
                current_step.status = StepStatus.COMPENSATED

            saga.updated_at = datetime.now(timezone.utc)
            await self._compensate_previous(saga, definition)
            await self._uow.sagas.update(saga)
            await self._uow.commit()

        return saga

    async def check_timeouts(self, max_age: timedelta) -> list[SagaInstance]:
        cutoff = datetime.now(timezone.utc) - max_age
        async with self._uow:
            stale_sagas = await self._uow.sagas.find_stale(older_than=cutoff)
            timed_out: list[SagaInstance] = []
            for saga in stale_sagas:
                saga.status = SagaStatus.TIMED_OUT
                saga.error_detail = f"Timed out after {max_age.total_seconds()}s"
                saga.completed_at = datetime.now(timezone.utc)
                saga.updated_at = datetime.now(timezone.utc)
                await self._uow.sagas.update(saga)
                timed_out.append(saga)
                logger.warning("Saga timed out: id=%s type=%s", saga.id, saga.saga_type)
            if timed_out:
                await self._uow.commit()
        return timed_out

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

            payload["saga_id"] = saga.id
            payload["saga_type"] = saga.saga_type
            payload["step_name"] = step.name
            payload["event_type"] = step_def.compensate_event_type
            await self._uow.outbox.add(
                event_type=step_def.compensate_event_type,
                payload_json=json.dumps(payload, default=str),
                aggregate_type="saga",
                aggregate_id=saga.id,
                correlation_id=saga.correlation_id,
            )
            return

        saga.status = SagaStatus.FAILED
        saga.completed_at = datetime.now(timezone.utc)
        logger.info("Saga compensation complete (failed): id=%s", saga.id)

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
