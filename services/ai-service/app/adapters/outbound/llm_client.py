"""Ollama client wrapper for answer generation."""

from __future__ import annotations

import logging
import re
import threading

from app.adapters.outbound.vectorstore import get_ollama_client
from app.config import settings

logger = logging.getLogger(__name__)

# Only allow one Ollama call at a time — prevents parallel requests from starving each other
_llm_lock = threading.Lock()

# Pattern to strip chain-of-thought leaking into the response
_THINK_PATTERN = re.compile(
    r"^(Okay|Let me|Let's|So|Looking|I need|I'll|Hmm|First|Now|The user).*?\n\n",
    re.DOTALL | re.IGNORECASE,
)


def _strip_thinking(text: str) -> str:
    """Remove leaked chain-of-thought from the beginning of model output."""
    cleaned = _THINK_PATTERN.sub("", text).strip()
    return cleaned if cleaned else text.strip()


def generate_answer(prompt: str) -> str:
    """Generate an answer using the configured local Ollama model."""
    if not _llm_lock.acquire(timeout=5):
        raise TimeoutError("En anden forespørgsel kører allerede — prøv igen om lidt")
    try:
        logger.info("Generating answer with local model %s", settings.LLM_MODEL)
        response = get_ollama_client().chat(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du er en dansk finansassistent. "
                        "Giv KUN det endelige svar. "
                        "Skriv ALDRIG dine tanker, overvejelser eller analyse. "
                        "Svar paa dansk med konkrete tal."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            think=False,
            options={
                "temperature": 0.1,
                "top_p": 0.9,
                "num_ctx": 1024,
                "num_predict": 120,
            },
        )
        raw = response.message.content.strip()
        return _strip_thinking(raw)
    finally:
        _llm_lock.release()
