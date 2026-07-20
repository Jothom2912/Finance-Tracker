"""No-op email adapter (email delivery deferred, F1-01 scope decision).

Implements :class:`IEmailPort` by logging what *would* be sent. Swap for a
real SMTP adapter later without touching the application layer.
"""

from __future__ import annotations

import logging

from app.application.ports.outbound import IEmailPort

logger = logging.getLogger(__name__)


class LogEmailAdapter(IEmailPort):
    async def send(self, *, user_id: int, title: str, body: str) -> None:
        logger.info(
            "email (no-op) → user=%s title=%r body=%r",
            user_id,
            title,
            body,
        )
