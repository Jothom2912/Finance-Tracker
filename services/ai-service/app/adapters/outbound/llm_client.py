"""Ollama client wrapper for answer generation."""

from __future__ import annotations

import logging

from app.adapters.outbound.vectorstore import get_ollama_client
from app.config import settings

logger = logging.getLogger(__name__)


def generate_answer(prompt: str) -> str:
    """Generate an answer using the configured local Ollama model."""
    logger.info("Generating answer with local model %s", settings.LLM_MODEL)
    response = get_ollama_client().chat(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Svar direkte paa brugerens spoergsmaal. "
                    "Vis ikke din interne analyse eller reasoning."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            }
        ],
        think=False,
        options={
            "temperature": 0.1,
            "top_p": 0.9,
            "num_ctx": 2048,
            "num_predict": 180,
        },
    )
    return response.message.content.strip()
