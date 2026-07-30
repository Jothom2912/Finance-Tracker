"""finans-tracker-observability — shared process-wide logging configuration.

See :mod:`observability.logging` for why an explicit configuration is required in every
API process (uvicorn configures only its own three loggers).
"""

from __future__ import annotations

from observability.logging import (
    LOG_FORMAT,
    UVICORN_LOGGERS,
    build_config,
    setup_logging,
)

__all__ = [
    "LOG_FORMAT",
    "UVICORN_LOGGERS",
    "build_config",
    "setup_logging",
]
