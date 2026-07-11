"""Worker logging setup.

Replaces the inline ``logging.basicConfig`` blocks copied into every
worker/consumer module.  Format matches the existing copies exactly so
log pipelines keep parsing.
"""

from __future__ import annotations

import logging

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def setup_worker_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure process-wide logging for a worker and return its logger.

    Idempotent: ``logging.basicConfig`` is a no-op when the root logger
    already has handlers, so calling this from several modules is safe.
    """
    logging.basicConfig(level=level, format=LOG_FORMAT)
    return logging.getLogger(name)
