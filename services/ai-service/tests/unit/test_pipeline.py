"""Unit tests for the pipeline orchestrator.

Mocks all external dependencies (router, dispatcher, responder) to verify:
- Correct event sequence
- Cancel handling via request.is_disconnected
- Error mapping from domain exceptions to ErrorEvents
- Fallback prose when responder yields nothing
- Latency metadata accumulation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.application.pipeline import run_pipeline
from app.domain.exceptions import AnalyticsAuthError, AnalyticsServiceUnavailableError
from app.domain.models import (
    DataKind,
    DataReadyData,
    DataReadyEvent,
    DoneEvent,
    ErrorEvent,
    IntentName,
    IntentResolvedEvent,
    ProseChunkEvent,
    ResolvedIntent,
    TransactionItem,
    TransactionListPayload,
)


def _mock_request(disconnected_after: int | None = None) -> MagicMock:
    """Create a mock Request. disconnected_after=N means is_disconnected returns
    True after N calls."""
    req = MagicMock()
    call_count = 0

    async def _is_disconnected() -> bool:
        nonlocal call_count
        call_count += 1
        if disconnected_after is not None and call_count > disconnected_after:
            return True
        return False

    req.is_disconnected = _is_disconnected
    return req


def _make_intent() -> ResolvedIntent:
    return ResolvedIntent(intent=IntentName.LARGEST_EXPENSE, period="2026-04")


def _make_data_ready() -> DataReadyData:
    return DataReadyData(
        kind=DataKind.TRANSACTION_LIST,
        payload=TransactionListPayload(
            items=[
                TransactionItem(
                    id=1, date="2026-04-27", amount=288.0,
                    category="Anden", description="TAXI 4X27",
                ),
            ],
            highlight_id=1,
        ),
    )


async def _collect_events(pipeline) -> list:
    return [event async for event in pipeline]


@patch("app.application.pipeline.OllamaRouter")
@patch("app.application.pipeline.dispatch")
@patch("app.application.pipeline.OllamaResponder")
@patch("app.application.pipeline.AnalyticsClient")
@patch("app.application.pipeline.ChromaDBSearch")
async def test_full_event_sequence(
    mock_search_cls: MagicMock,
    mock_analytics_cls: MagicMock,
    mock_responder_cls: MagicMock,
    mock_dispatch: AsyncMock,
    mock_router_cls: MagicMock,
) -> None:
    mock_router_cls.return_value.classify_intent = AsyncMock(
        return_value=(_make_intent(), 100.0),
    )
    mock_dispatch.return_value = (_make_data_ready(), 50.0)

    async def _fake_stream(*args, **kwargs):
        yield "Din "
        yield "største "
        yield "udgift."

    mock_responder_cls.return_value.stream_response = _fake_stream

    events = await _collect_events(
        run_pipeline("test", 1, 1, "token", _mock_request()),
    )

    assert isinstance(events[0], IntentResolvedEvent)
    assert isinstance(events[1], DataReadyEvent)
    assert isinstance(events[2], ProseChunkEvent)
    assert events[2].data.delta == "Din "
    assert isinstance(events[3], ProseChunkEvent)
    assert isinstance(events[4], ProseChunkEvent)
    assert isinstance(events[-1], DoneEvent)

    metadata = events[-1].data.metadata
    assert metadata.router_ms == 100.0
    assert metadata.dispatch_ms == 50.0
    assert metadata.responder_ms >= 0
    assert metadata.total_tokens == 3


@patch("app.application.pipeline.OllamaRouter")
@patch("app.application.pipeline.dispatch")
@patch("app.application.pipeline.OllamaResponder")
@patch("app.application.pipeline.AnalyticsClient")
@patch("app.application.pipeline.ChromaDBSearch")
async def test_cancel_after_routing(
    mock_search_cls: MagicMock,
    mock_analytics_cls: MagicMock,
    mock_responder_cls: MagicMock,
    mock_dispatch: AsyncMock,
    mock_router_cls: MagicMock,
) -> None:
    mock_router_cls.return_value.classify_intent = AsyncMock(
        return_value=(_make_intent(), 100.0),
    )

    events = await _collect_events(
        run_pipeline("test", 1, 1, "token", _mock_request(disconnected_after=0)),
    )

    assert len(events) == 1
    assert isinstance(events[0], IntentResolvedEvent)
    mock_dispatch.assert_not_awaited()


@patch("app.application.pipeline.OllamaRouter")
@patch("app.application.pipeline.dispatch")
@patch("app.application.pipeline.OllamaResponder")
@patch("app.application.pipeline.AnalyticsClient")
@patch("app.application.pipeline.ChromaDBSearch")
async def test_cancel_after_dispatch(
    mock_search_cls: MagicMock,
    mock_analytics_cls: MagicMock,
    mock_responder_cls: MagicMock,
    mock_dispatch: AsyncMock,
    mock_router_cls: MagicMock,
) -> None:
    mock_router_cls.return_value.classify_intent = AsyncMock(
        return_value=(_make_intent(), 100.0),
    )
    mock_dispatch.return_value = (_make_data_ready(), 50.0)

    events = await _collect_events(
        run_pipeline("test", 1, 1, "token", _mock_request(disconnected_after=1)),
    )

    assert len(events) == 2
    assert isinstance(events[0], IntentResolvedEvent)
    assert isinstance(events[1], DataReadyEvent)


@patch("app.application.pipeline.OllamaRouter")
@patch("app.application.pipeline.AnalyticsClient")
@patch("app.application.pipeline.ChromaDBSearch")
async def test_analytics_auth_error_emits_error_event(
    mock_search_cls: MagicMock,
    mock_analytics_cls: MagicMock,
    mock_router_cls: MagicMock,
) -> None:
    mock_router_cls.return_value.classify_intent = AsyncMock(
        return_value=(_make_intent(), 100.0),
    )

    with patch(
        "app.application.pipeline.dispatch",
        side_effect=AnalyticsAuthError("Token expired", status_code=401),
    ):
        events = await _collect_events(
            run_pipeline("test", 1, 1, "token", _mock_request()),
        )

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].data.code == "auth_error"


@patch("app.application.pipeline.OllamaRouter")
@patch("app.application.pipeline.AnalyticsClient")
@patch("app.application.pipeline.ChromaDBSearch")
async def test_service_unavailable_emits_error_event(
    mock_search_cls: MagicMock,
    mock_analytics_cls: MagicMock,
    mock_router_cls: MagicMock,
) -> None:
    mock_router_cls.return_value.classify_intent = AsyncMock(
        return_value=(_make_intent(), 100.0),
    )

    with patch(
        "app.application.pipeline.dispatch",
        side_effect=AnalyticsServiceUnavailableError("Down", status_code=503),
    ):
        events = await _collect_events(
            run_pipeline("test", 1, 1, "token", _mock_request()),
        )

    error_events = [e for e in events if isinstance(e, ErrorEvent)]
    assert len(error_events) == 1
    assert error_events[0].data.code == "service_unavailable"


@patch("app.application.pipeline.OllamaRouter")
@patch("app.application.pipeline.dispatch")
@patch("app.application.pipeline.OllamaResponder")
@patch("app.application.pipeline.AnalyticsClient")
@patch("app.application.pipeline.ChromaDBSearch")
async def test_empty_responder_yields_fallback(
    mock_search_cls: MagicMock,
    mock_analytics_cls: MagicMock,
    mock_responder_cls: MagicMock,
    mock_dispatch: AsyncMock,
    mock_router_cls: MagicMock,
) -> None:
    mock_router_cls.return_value.classify_intent = AsyncMock(
        return_value=(_make_intent(), 100.0),
    )
    mock_dispatch.return_value = (_make_data_ready(), 50.0)

    async def _empty_stream(*args, **kwargs):
        return
        yield

    mock_responder_cls.return_value.stream_response = _empty_stream

    events = await _collect_events(
        run_pipeline("test", 1, 1, "token", _mock_request()),
    )

    prose_events = [e for e in events if isinstance(e, ProseChunkEvent)]
    assert len(prose_events) == 1
    assert "kunne ikke formulere" in prose_events[0].data.delta


@patch("app.application.pipeline.OllamaRouter")
@patch("app.application.pipeline.dispatch")
@patch("app.application.pipeline.OllamaResponder")
@patch("app.application.pipeline.AnalyticsClient")
@patch("app.application.pipeline.ChromaDBSearch")
async def test_latency_metadata_populated(
    mock_search_cls: MagicMock,
    mock_analytics_cls: MagicMock,
    mock_responder_cls: MagicMock,
    mock_dispatch: AsyncMock,
    mock_router_cls: MagicMock,
) -> None:
    mock_router_cls.return_value.classify_intent = AsyncMock(
        return_value=(_make_intent(), 123.4),
    )
    mock_dispatch.return_value = (_make_data_ready(), 56.7)

    async def _one_token(*args, **kwargs):
        yield "Svar."

    mock_responder_cls.return_value.stream_response = _one_token

    events = await _collect_events(
        run_pipeline("test", 1, 1, "token", _mock_request()),
    )

    done = [e for e in events if isinstance(e, DoneEvent)]
    assert len(done) == 1
    meta = done[0].data.metadata
    assert meta.router_ms == 123.4
    assert meta.dispatch_ms == 56.7
    assert meta.responder_ms >= 0
    assert meta.total_tokens == 1
