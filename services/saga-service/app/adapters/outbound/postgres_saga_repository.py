from __future__ import annotations

import json
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.outbound import ISagaRepository
from app.domain.entities import SagaInstance, SagaStatus, SagaStep, StepStatus
from app.models import SagaInstanceModel, SagaStepLogModel

logger = logging.getLogger(__name__)


class PostgresSagaRepository(ISagaRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, saga: SagaInstance) -> None:
        model = SagaInstanceModel(
            id=saga.id,
            saga_type=saga.saga_type,
            correlation_id=saga.correlation_id,
            current_step=saga.current_step,
            status=saga.status.value,
            context_json=json.dumps(saga.context, default=str),
            error_detail=saga.error_detail,
            started_at=saga.started_at,
            completed_at=saga.completed_at,
            updated_at=saga.updated_at,
        )
        self._session.add(model)
        await self._session.flush()

        for step in saga.steps:
            step_model = SagaStepLogModel(
                id=str(uuid4()),
                saga_id=saga.id,
                step_index=step.index,
                step_name=step.name,
                status=step.status.value,
                command_sent_at=step.command_sent_at,
                reply_received_at=step.reply_received_at,
                compensated_at=step.compensated_at,
                error_detail=step.error_detail,
            )
            self._session.add(step_model)
        await self._session.flush()

    async def get_by_id(self, saga_id: str, *, for_update: bool = False) -> SagaInstance | None:
        stmt = select(SagaInstanceModel).where(SagaInstanceModel.id == saga_id)
        if for_update:
            # Lock the saga row until the surrounding transaction commits.
            # Step rows are only ever mutated while holding this parent-row
            # lock, so locking saga_instances alone serializes all
            # read-modify-write paths (reply handling, compensation replies,
            # timeout marking).
            stmt = stmt.with_for_update()
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None

        steps_result = await self._session.execute(
            select(SagaStepLogModel).where(SagaStepLogModel.saga_id == saga_id).order_by(SagaStepLogModel.step_index)
        )
        step_models = steps_result.scalars().all()

        return self._to_entity(model, list(step_models))

    async def get_by_correlation_id(self, correlation_id: str) -> SagaInstance | None:
        result = await self._session.execute(
            select(SagaInstanceModel).where(SagaInstanceModel.correlation_id == correlation_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None

        steps_result = await self._session.execute(
            select(SagaStepLogModel).where(SagaStepLogModel.saga_id == model.id).order_by(SagaStepLogModel.step_index)
        )
        step_models = steps_result.scalars().all()
        return self._to_entity(model, list(step_models))

    async def find_stale_ids(self, older_than: datetime) -> list[str]:
        # Deliberately fetches only ids: no context_json, no per-saga step
        # queries. Full state is loaded (under a row lock) only for sagas
        # that actually need action.
        result = await self._session.execute(
            select(SagaInstanceModel.id).where(
                SagaInstanceModel.status.in_(["started", "compensating"]),
                SagaInstanceModel.updated_at <= older_than,
            )
        )
        return list(result.scalars().all())

    async def update(self, saga: SagaInstance) -> None:
        await self._session.execute(
            update(SagaInstanceModel)
            .where(SagaInstanceModel.id == saga.id)
            .values(
                current_step=saga.current_step,
                status=saga.status.value,
                context_json=json.dumps(saga.context, default=str),
                error_detail=saga.error_detail,
                completed_at=saga.completed_at,
                updated_at=saga.updated_at,
            )
        )
        for step in saga.steps:
            await self._session.execute(
                update(SagaStepLogModel)
                .where(
                    SagaStepLogModel.saga_id == saga.id,
                    SagaStepLogModel.step_index == step.index,
                )
                .values(
                    status=step.status.value,
                    command_sent_at=step.command_sent_at,
                    reply_received_at=step.reply_received_at,
                    compensated_at=step.compensated_at,
                    error_detail=step.error_detail,
                )
            )

    @staticmethod
    def _to_entity(model: SagaInstanceModel, step_models: list[SagaStepLogModel]) -> SagaInstance:
        steps = [
            SagaStep(
                index=s.step_index,
                name=s.step_name,
                status=StepStatus(s.status),
                command_sent_at=s.command_sent_at,
                reply_received_at=s.reply_received_at,
                compensated_at=s.compensated_at,
                error_detail=s.error_detail,
            )
            for s in step_models
        ]
        return SagaInstance(
            id=model.id,
            saga_type=model.saga_type,
            correlation_id=model.correlation_id,
            current_step=model.current_step,
            status=SagaStatus(model.status),
            context=json.loads(model.context_json) if model.context_json else {},
            steps=steps,
            error_detail=model.error_detail,
            started_at=model.started_at,
            completed_at=model.completed_at,
            updated_at=model.updated_at,
        )
