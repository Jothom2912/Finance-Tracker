"""Integration test — full pipeline with mocked Ollama and HTTP clients.

Verifies the entire event sequence end-to-end: router → dispatcher →
responder, with only external I/O mocked (Ollama SDK, httpx).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.application.pipeline import run_pipeline
from app.domain.models import (
    DataReadyEvent,
    DoneEvent,
    IntentResolvedEvent,
    ProseChunkEvent,
)


def _mock_request() -> MagicMock:
    req = MagicMock()
    req.is_disconnected = AsyncMock(return_value=False)
    return req


def _mock_ollama_chat_response(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    resp = MagicMock()
    resp.message = msg
    return resp


def _mock_ollama_stream_chunks(tokens: list[str]) -> list[MagicMock]:
    chunks = []
    for token in tokens:
        chunk = MagicMock()
        chunk.message = MagicMock()
        chunk.message.content = token
        chunks.append(chunk)
    return chunks


@patch("app.adapters.outbound.analytics_client.httpx.AsyncClient")
@patch("app.adapters.outbound.ollama_router.get_ollama_client")
@patch("app.adapters.outbound.ollama_responder.get_ollama_client")
async def test_largest_expense_end_to_end(
    mock_responder_ollama: MagicMock,
    mock_router_ollama: MagicMock,
    mock_httpx: MagicMock,
) -> None:
    """Acceptance test: "Hvad er min største udgift i april 2026?" """

    # Router returns largest_expense intent
    mock_router_ollama.return_value.chat.return_value = _mock_ollama_chat_response(
        '{"intent": "largest_expense", "period": "2026-04", "slots": {}}'
    )

    # Transaction-service returns expenses
    mock_http_response = MagicMock()
    mock_http_response.is_success = True
    mock_http_response.json.return_value = [
        {
            "id": 42,
            "date": "2026-04-27",
            "amount": "-288.00",
            "category_name": "Anden",
            "description": "TAXI 4X27",
            "transaction_type": "expense",
        },
        {
            "id": 43,
            "date": "2026-04-15",
            "amount": "-150.00",
            "category_name": "Dagligvarer",
            "description": "Netto",
            "transaction_type": "expense",
        },
    ]

    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_http_response
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)
    mock_httpx.return_value = mock_client_instance

    # Responder streams prose
    stream_chunks = _mock_ollama_stream_chunks([
        "Din ", "største ", "udgift ", "i ", "april ", "var ",
        "TAXI ", "4X27 ", "på ", "288,00 ", "kr.",
    ])
    mock_responder_ollama.return_value.chat.return_value = iter(stream_chunks)

    events = []
    async for event in run_pipeline(
        question="Hvad er min største udgift i april 2026?",
        user_id=1,
        account_id=1,
        token="test-token",
        request=_mock_request(),
    ):
        events.append(event)

    # Verify event sequence
    assert isinstance(events[0], IntentResolvedEvent)
    assert events[0].data.intent.value == "largest_expense"
    assert events[0].data.period == "2026-04"

    assert isinstance(events[1], DataReadyEvent)
    assert events[1].data.kind.value == "transaction_list"
    assert events[1].data.payload.highlight_id == 42
    assert len(events[1].data.payload.items) == 2
    assert events[1].data.payload.items[0].amount == 288.0

    prose_events = [e for e in events if isinstance(e, ProseChunkEvent)]
    assert len(prose_events) == 11
    full_prose = "".join(e.data.delta for e in prose_events)
    assert "288,00" in full_prose

    assert isinstance(events[-1], DoneEvent)
    meta = events[-1].data.metadata
    assert meta.router_ms > 0
    assert meta.dispatch_ms > 0
    assert meta.responder_ms >= 0
    assert meta.total_tokens == 11
