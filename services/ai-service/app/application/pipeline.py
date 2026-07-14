"""3-step streaming pipeline: router → dispatcher → responder.

Orchestrates the chat flow as an async generator of typed ChatStreamEvents.
Each step produces one or more events that serialize directly to SSE frames.
Pipeline owns latency measurement for responder (wall-clock around iterator)
and aggregates per-step timings from adapters into StreamMetadata.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import TypeAlias

from starlette.requests import Request

from app.adapters.outbound.analytics_client import AnalyticsClient
from app.adapters.outbound.chromadb_search import ChromaDBSearch
from app.adapters.outbound.es_search import EsSearch
from app.adapters.outbound.ollama_responder import OllamaResponder
from app.adapters.outbound.ollama_router import OllamaRouter
from app.application.intent_dispatcher import dispatch
from app.application.ports.semantic_search_port import ISemanticSearchPort
from app.config import settings
from app.domain.exceptions import (
    AnalyticsAuthError,
    AnalyticsError,
    AnalyticsNotFoundError,
    AnalyticsServiceUnavailableError,
)
from app.domain.models import (
    BudgetStatusPayload,
    CategoryBreakdownPayload,
    DataReadyData,
    DataReadyEvent,
    DoneData,
    DoneEvent,
    ErrorData,
    ErrorEvent,
    IntentResolvedEvent,
    ProseChunkData,
    ProseChunkEvent,
    SingleValuePayload,
    StreamMetadata,
    TransactionListPayload,
)

logger = logging.getLogger(__name__)

PipelineEvent: TypeAlias = IntentResolvedEvent | DataReadyEvent | ProseChunkEvent | DoneEvent | ErrorEvent


def build_search(user_id: int, token: str) -> ISemanticSearchPort:
    """AI-20 cutover-seam: SEARCH_BACKEND vælger semantic search-adapter."""
    if settings.SEARCH_BACKEND == "es":
        return EsSearch(user_id=user_id, token=token)
    return ChromaDBSearch(user_id=user_id)


async def run_pipeline(
    question: str,
    user_id: int,
    account_id: int,
    token: str,
    request: Request,
) -> AsyncIterator[PipelineEvent]:
    """Run the 3-step chat pipeline, yielding typed events for SSE streaming."""
    router = OllamaRouter()
    responder = OllamaResponder()
    analytics = AnalyticsClient(token=token, account_id=account_id)
    search = build_search(user_id=user_id, token=token)

    router_ms = 0.0
    dispatch_ms = 0.0
    responder_ms = 0.0
    total_tokens = 0

    try:
        # --- Step 1: Route ---
        intent, router_ms = await router.classify_intent(question)
        yield IntentResolvedEvent(data=intent)

        if await request.is_disconnected():
            logger.warning("Client disconnected after routing")
            return

        # --- Step 2: Dispatch ---
        data_ready, dispatch_ms = await dispatch(intent, analytics, search)
        yield DataReadyEvent(data=data_ready)

        if await request.is_disconnected():
            logger.warning("Client disconnected after dispatch")
            return

        # --- Step 3: Respond (streaming) ---
        data_context = _format_data_context(data_ready)
        t_responder = time.perf_counter()

        async for delta in responder.stream_response(question, data_context):
            total_tokens += 1
            yield ProseChunkEvent(data=ProseChunkData(delta=delta))

        responder_ms = (time.perf_counter() - t_responder) * 1000

        if total_tokens == 0:
            logger.warning("Responder produced no content tokens")
            yield ProseChunkEvent(
                data=ProseChunkData(delta="Jeg kunne ikke formulere et svar baseret på data."),
            )

    except AnalyticsAuthError as exc:
        logger.warning("Auth error in pipeline: %s", exc)
        yield ErrorEvent(data=ErrorData(code="auth_error", message="Token er udløbet eller ugyldigt."))
        return
    except AnalyticsNotFoundError as exc:
        logger.warning("Not found in pipeline: %s", exc)
        yield ErrorEvent(data=ErrorData(code="not_found", message="Data blev ikke fundet for den valgte periode."))
        return
    except AnalyticsServiceUnavailableError as exc:
        logger.error("Service unavailable in pipeline: %s", exc)
        yield ErrorEvent(
            data=ErrorData(
                code="service_unavailable", message="En bagvedliggende tjeneste er midlertidigt utilgængelig."
            )
        )
        return
    except AnalyticsError as exc:
        logger.error("Analytics error in pipeline: %s", exc)
        yield ErrorEvent(data=ErrorData(code="analytics_error", message="Kunne ikke hente data."))
        return
    except ValueError as exc:
        logger.error("Validation error in pipeline: %s", exc)
        yield ErrorEvent(data=ErrorData(code="validation_error", message="Ugyldig forespørgsel."))
        return
    except Exception:
        logger.exception("Unexpected error in pipeline")
        yield ErrorEvent(data=ErrorData(code="internal_error", message="En uventet fejl opstod."))
        return

    # --- Done ---
    yield DoneEvent(
        data=DoneData(
            metadata=StreamMetadata(
                router_ms=round(router_ms, 1),
                dispatch_ms=round(dispatch_ms, 1),
                responder_ms=round(responder_ms, 1),
                total_tokens=total_tokens,
            ),
        ),
    )


def _format_data_context(data: DataReadyData) -> str:
    """Format dispatched data as text context for the responder model.

    Structured enough for the model to extract facts, but not so verbose
    that it wastes context window. The responder uses this to formulate
    a 2-3 sentence Danish summary — it should NOT repeat the raw data.
    """
    payload = data.payload

    if isinstance(payload, TransactionListPayload):
        if not payload.items:
            return "Ingen transaktioner fundet."
        lines = []
        for t in payload.items:
            lines.append(f"- {t.date}: {t.amount:.2f} kr, {t.category}, {t.description}")
        if payload.highlight_id is not None:
            lines.append(f"Fremhævet transaktion: ID {payload.highlight_id}")
        return "TRANSAKTIONER:\n" + "\n".join(lines)

    if isinstance(payload, CategoryBreakdownPayload):
        lines = [f"- {item.category}: {item.amount:.2f} kr ({item.percentage}%)" for item in payload.items]
        lines.append(f"Total: {payload.total:.2f} kr")
        return "KATEGORIFORDELING:\n" + "\n".join(lines)

    if isinstance(payload, SingleValuePayload):
        return f"{payload.label}: {payload.value:.2f} {payload.currency}"

    if isinstance(payload, BudgetStatusPayload):
        lines = []
        for item in payload.items:
            status = "OVER" if item.remaining_amount < 0 else "OK"
            lines.append(
                f"- {item.category_name}: budget {item.budget_amount:.2f} kr, "
                f"brugt {item.spent_amount:.2f} kr ({item.percentage_used:.0f}%) [{status}]"
            )
        lines.append(
            f"Total: budget {payload.total_budget:.2f} kr, "
            f"brugt {payload.total_spent:.2f} kr, "
            f"resterende {payload.total_remaining:.2f} kr"
        )
        if payload.over_budget_count > 0:
            lines.append(f"{payload.over_budget_count} kategorier er over budget.")
        return "BUDGETSTATUS:\n" + "\n".join(lines)

    return str(payload)
