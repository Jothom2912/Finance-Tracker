from __future__ import annotations

import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from observability import setup_logging

from app.auth import get_current_user_id

# P3-57: uvicorn konfigurerer kun sine egne loggere — uden dette arver app.* root's WARNING.
setup_logging()

# P3-59: servicens tre eksisterende warnings ligger i orchestratoren. Loggeren her hører
# til API-processen — og med vilje i `main.py`, ikke i `postgres_saga_repository.py:15`s
# ubrugte logger: den fil importeres af alle fire workers, så en linje dér ville fyre i
# fem processer og gøre det umuligt at se hvad der kom fra en request.
logger = logging.getLogger(__name__)

app = FastAPI(title="Saga Service")


# Context keys stripped from API responses: bulky and/or sensitive payload data
# (e.g. every synced bank transaction after the fetch step).
EXCLUDED_CONTEXT_KEYS = {"fetched_items", "items"}


def _sanitize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if not context:
        return {}
    return {k: v for k, v in context.items() if k not in EXCLUDED_CONTEXT_KEYS}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy", "service": "saga-service"}


@app.get("/api/v1/sagas/{saga_id}")
async def get_saga_status(saga_id: str, user_id: int = Depends(get_current_user_id)) -> dict:
    from app.adapters.outbound.postgres_saga_repository import PostgresSagaRepository
    from app.database import async_session_factory

    async with async_session_factory() as session:
        repo = PostgresSagaRepository(session)
        instance = await repo.get_by_id(saga_id)
        if instance is None:
            instance = await repo.get_by_correlation_id(saga_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="Saga not found")

        # The missing-key case is spelled out rather than left to int(None) raising
        # TypeError: the except still has work to do (a non-numeric or list value),
        # but relying on it for the common "no user_id in context" path made the
        # annotation false. Both routes land on owner_id = None and a 403.
        raw_owner_id = (instance.context or {}).get("user_id")
        try:
            owner_id = int(raw_owner_id) if raw_owner_id is not None else None
        except (TypeError, ValueError):
            owner_id = None
        if owner_id is None or owner_id != user_id:
            # P3-59: den ene 403 har tre årsager, og de kræver *modsatte* handlinger.
            # De to første er data-integritetssignaler: en saga uden ejer i konteksten er
            # ikke tilgængelig for nogen, hvilket er en bug hos den der startede den. Den
            # tredje er et sikkerhedssignal. Samme respons, samme statuskode — så uden
            # denne linje er de ikke til at skelne, hverken fra hinanden eller fra et probe.
            #
            # Værdien logges KUN i den korrupte gren, hvor den er hele signalet (typisk en
            # liste eller en streng hvor et heltal var forventet). I krydstenant-grenen
            # logges ejerens id, ikke noget fra requesten.
            if raw_owner_id is None:
                logger.warning(
                    "Afvist saga-opslag (403): saga %s har intet user_id i sin kontekst "
                    "— utilgængelig for alle, bruger %s spurgte",
                    instance.id,
                    user_id,
                )
            elif owner_id is None:
                logger.warning(
                    "Afvist saga-opslag (403): saga %s har et korrupt user_id i konteksten (%r) — bruger %s spurgte",
                    instance.id,
                    raw_owner_id,
                    user_id,
                )
            else:
                logger.warning(
                    "Afvist saga-opslag (403): bruger %s forsøgte saga %s (ejet af %s)",
                    user_id,
                    instance.id,
                    owner_id,
                )
            raise HTTPException(status_code=403, detail="Access denied")

        current_step_name = None
        if instance.steps and 0 <= instance.current_step < len(instance.steps):
            current_step_name = instance.steps[instance.current_step].name

        return {
            "saga_id": instance.id,
            "saga_type": instance.saga_type,
            "status": instance.status.value,
            "current_step": instance.current_step,
            "current_step_name": current_step_name,
            "context": _sanitize_context(instance.context),
            "error_detail": instance.error_detail,
            "started_at": instance.started_at.isoformat() if instance.started_at else None,
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None,
        }
