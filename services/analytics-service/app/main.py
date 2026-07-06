from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.outbound.elasticsearch.bootstrap import ensure_indices
from app.adapters.outbound.elasticsearch.client import create_es_client
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Fail-fast hvis ES er nede ved opstart: compose/k8s venter på healthy
    # ES, og en app uden read-store kan alligevel intet svare.
    es = create_es_client(settings)
    await ensure_indices(es, settings.es_index_prefix)
    app.state.es = es
    try:
        yield
    finally:
        await es.close()


app = FastAPI(title="Analytics Service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "analytics-service"}
