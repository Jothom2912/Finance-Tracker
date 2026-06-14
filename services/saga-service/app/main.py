from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app = FastAPI(title="Saga Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "saga-service"}


@app.get("/api/v1/sagas/{saga_id}")
async def get_saga_status(saga_id: str) -> dict:
    from app.adapters.outbound.postgres_saga_repository import PostgresSagaRepository
    from app.database import async_session_factory

    async with async_session_factory() as session:
        repo = PostgresSagaRepository(session)
        instance = await repo.get_by_id(saga_id)
        if instance is None:
            instance = await repo.get_by_correlation_id(saga_id)
        if instance is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Saga not found")

        current_step_name = None
        if instance.steps and 0 <= instance.current_step < len(instance.steps):
            current_step_name = instance.steps[instance.current_step].name

        return {
            "saga_id": instance.id,
            "saga_type": instance.saga_type,
            "status": instance.status.value,
            "current_step": instance.current_step,
            "current_step_name": current_step_name,
            "context": instance.context,
            "error_detail": instance.error_detail,
            "started_at": instance.started_at.isoformat() if instance.started_at else None,
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
        }
