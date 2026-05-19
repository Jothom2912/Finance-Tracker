"""Ollama router adapter — classifies user questions into intents.

Uses constrained sampling (format=schema) to guarantee valid JSON output.
think=False because classification doesn't benefit from chain-of-thought,
and the 4B model is chosen for latency over quality — the JSON structure
is enforced by the schema, not by model reasoning.

System prompt er på dansk fordi Qwen3 producerer mest konsistente output
når instruktionssproget matcher input-sproget. Det reducerer risiko for
sprog-mixing i slot-værdier (fx at modellen skriver "groceries" i stedet
for "dagligvarer" som category-slot), hvilket ellers ville bryde
downstream metadata-filtre der matcher på danske kategori-navne.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import anyio
from pydantic import ValidationError

from app.adapters.outbound.vectorstore import get_ollama_client
from app.config import settings
from app.domain.models import IntentName, ResolvedIntent

logger = logging.getLogger(__name__)

_INTENT_SCHEMA = ResolvedIntent.model_json_schema()

_ROUTER_SYSTEM_PROMPT_TEMPLATE = """\
Du er en intent-router for en dansk finansassistent.
Klassificér brugerens spørgsmål til præcis én intent.

Intents:
- largest_expense: Største udgift i en periode, evt. filtreret på kategori
- category_breakdown: Fordeling af udgifter per kategori i en periode
- transaction_search: Søgning efter specifikke transaktioner (semantisk)
- budget_status: Budget vs. faktisk forbrug i en periode

Regler:
- period: YYYY-MM format baseret på spørgsmålet. Default {current_period} hvis uklart.
- slots: Ekstra parametre som JSON-objekt. Eksempler:
  - {{"category": "dagligvarer"}} for kategori-filter
  - {{"query": "kaffe"}} for søgeterm
  - {{}} hvis ingen ekstra parametre
"""


class OllamaRouter:
    async def classify_intent(self, question: str) -> tuple[ResolvedIntent, float]:
        """Classify a question into a structured intent via constrained sampling.

        Returns (intent, elapsed_ms).
        """
        t0 = time.monotonic()
        current_period = datetime.now().strftime("%Y-%m")
        system_prompt = _ROUTER_SYSTEM_PROMPT_TEMPLATE.format(current_period=current_period)

        def _call() -> str:
            response = get_ollama_client().chat(
                model=settings.LLM_ROUTER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                think=False,
                format=_INTENT_SCHEMA,
                options={
                    "temperature": 0.1,
                    "num_ctx": 2048,
                    "num_predict": 256,
                },
                keep_alive=settings.LLM_ROUTER_KEEP_ALIVE,
            )
            return response.message.content

        raw = await anyio.to_thread.run_sync(_call)
        elapsed_ms = (time.monotonic() - t0) * 1000

        try:
            intent = ResolvedIntent.model_validate_json(raw)
        except ValidationError:
            logger.warning("Router output failed validation, falling back to transaction_search: %s", raw)
            intent = ResolvedIntent(
                intent=IntentName.TRANSACTION_SEARCH,
                period=current_period,
                slots={"query": question},
            )

        logger.info("Router classified in %.0fms: %s", elapsed_ms, intent.intent.value)
        return intent, elapsed_ms
