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
TRAITS:
Du er en præcis intent-klassificeringsmotor for en dansk finansassistent.
Du er deterministisk, hurtig og vælger altid præcis én intent.

TASK:
Klassificér brugerens spørgsmål til én af følgende intents:
- largest_expense: Største udgift i en periode UDEN emne-filter. Kun når brugeren spørger "hvad er min største udgift?" uden at nævne en type, kategori eller vare.
- category_breakdown: Fordeling af udgifter per kategori i en periode
- transaction_search: Søgning efter transaktioner. Brug ALTID denne når brugeren nævner et emne, en type, en vare, en butik eller en kategori (fx "mad", "kaffe", "tøj", "Netto", "restaurant", "transport")
- budget_status: Budget vs. faktisk forbrug i en periode

Eksempler:
- "Hvad er min største udgift i maj?" → largest_expense, slots={{}}
- "Hvad bruger jeg på mad?" → transaction_search, slots={{"query": "mad"}}
- "Største udgift på mad i maj" → transaction_search, slots={{"query": "største udgift mad"}}
- "Hvor meget går til kaffe?" → transaction_search, slots={{"query": "kaffe"}}
- "Vis mine restaurantudgifter" → transaction_search, slots={{"query": "restaurant"}}

Regler:
- period: YYYY-MM format. Default {current_period} hvis uklart.
- slots: transaction_search bruger {{"query": "..."}}, andre intents bruger {{}}

TONE:
Strengt struktureret. Output er KUN valid JSON — ingen prosa, ingen forklaring.

TARGET:
En downstream pipeline der parser dit JSON-output maskinelt.
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
