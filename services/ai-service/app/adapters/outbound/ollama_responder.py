"""Ollama responder adapter — streams Danish prose summaries.

Uses think=True so the model reasons internally before answering, but ONLY
message.content is yielded to the caller. message.thinking is explicitly
discarded because: (1) thinking tokens are in English and would violate the
Danish-only contract, (2) they contain methodology explanations ("First, I
need to...") that the frontend must never show, and (3) the separation lets
us measure responder latency on actual user-visible output only.

System prompt er på dansk af samme grund som routeren: Qwen3 producerer
mest konsistente output når instruktionssproget matcher input-sproget,
og det reducerer risiko for sprog-mixing i det streamede svar.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import anyio
import anyio.from_thread

from app.adapters.outbound.ollama_client import get_ollama_client
from app.config import settings

logger = logging.getLogger(__name__)

_RESPONDER_SYSTEM_PROMPT = """\
TRAITS:
Du er en erfaren dansk finansassistent med speciale i personlig økonomi.
Du er præcis med tal, ærlig når data mangler, og svarer kun ud fra de data du modtager.

TASK:
Opsummér de leverede finansdata som et kort, direkte svar på brugerens spørgsmål.
- Max 2-3 korte sætninger
- Beløb skrives som: 288,00 kr (komma som decimal, kr efter beløb)
- Datoer skrives som: 21. april 2026
- Gentag IKKE transaktionslister — data vises separat i brugerfladen
- Forklar IKKE din metode ("Jeg har gennemgået..." er forbudt)

TONE:
Professionel men uformel. Svar KUN på dansk — ingen engelske ord eller fraser.
Giv et direkte, konkret svar uden indledende fraser.

TARGET:
En privatperson uden regnskabsbaggrund, som vil forstå sit forbrugsmønster.
Undgå fagtermer og forklar med hverdagssprog.
"""


class OllamaResponder:
    async def stream_response(
        self,
        question: str,
        data_context: str,
    ) -> AsyncIterator[str]:
        """Stream prose response tokens, yielding only content (not thinking).

        Pipeline measures wall-clock time around this iterator for latency
        metadata — adapter owns no timing concerns.
        """
        send_chan, recv_chan = anyio.create_memory_object_stream[str](max_buffer_size=64)

        async def _produce() -> None:
            try:

                def _stream_sync() -> None:
                    stream = get_ollama_client().chat(
                        model=settings.LLM_RESPONDER_MODEL,
                        messages=[
                            {"role": "system", "content": _RESPONDER_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": (f"DATA:\n{data_context}\n\nBRUGERENS SPØRGSMÅL:\n{question}"),
                            },
                        ],
                        think=True,
                        stream=True,
                        options={
                            "temperature": 0.3,
                            "num_ctx": 8192,
                            "num_predict": 2048,
                        },
                        keep_alive=settings.LLM_RESPONDER_KEEP_ALIVE,
                    )
                    for chunk in stream:
                        # Discard thinking tokens — see module docstring for why
                        content = chunk.message.content
                        if content:
                            # Backpressure: blocks thread until consumer reads a chunk,
                            # preventing WouldBlock if Ollama streams faster than SSE client
                            anyio.from_thread.run(send_chan.send, content)

                await anyio.to_thread.run_sync(_stream_sync)
            finally:
                send_chan.close()

        async with anyio.create_task_group() as tg:
            tg.start_soon(_produce)
            async for delta in recv_chan:
                yield delta
