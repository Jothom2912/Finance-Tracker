"""Process-wide logging configuration.

One entry point for both kinds of process in this repo:

* **API processes** (``uvicorn app.main:app``) — uvicorn configures *only* its own three
  loggers and leaves the root logger with zero handlers at level ``WARNING``.  Everything
  under ``app.*`` inherits that, so ``logger.info`` dies on the level check and
  ``logger.warning`` escapes to ``logging.lastResort``: a handler with no formatter that
  writes the *bare message* to stderr.  ``grep WARNING`` then returns nothing even when
  warnings fired, which is worse than silence — see P3-57.
* **Workers** — reached through ``messaging.setup_worker_logging``, which delegates here.

Call :func:`setup_logging` at *module level* in ``app/main.py``, before the first
``logging.getLogger`` call.  Module level and not ``lifespan``: uvicorn configures logging in
``Config.__init__``, i.e. *before* the app is imported, so an import-time call lands after
uvicorn's and wins — while a ``lifespan`` call would run after every module-level logger has
already been created.
"""

from __future__ import annotations

import logging
import logging.config
import os
from typing import Any

# Kept byte-identical to the format the 23 worker call sites have always used, so log
# pipelines parse the same lines before and after this package existed.  No ``datefmt``:
# the default gives ``asctime`` millisecond precision, and dropping it would be a silent
# loss of resolution.
LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"

#: uvicorn's own loggers.  We declare them with no handlers of their own and
#: ``propagate: True`` so their records reach the root handler and get *our* formatter.
#: Without this they keep uvicorn's ``INFO:     ...`` format, and access lines stay
#: un-greppable by level — which would leave the whole point half-solved.
UVICORN_LOGGERS = ("uvicorn", "uvicorn.access", "uvicorn.error")

DEFAULT_LEVEL = "INFO"


def _resolve_level(level: str | int | None) -> str | int:
    """Fall back to ``LOG_LEVEL`` from the environment, then to :data:`DEFAULT_LEVEL`.

    Reading the environment here rather than in each service's ``config.py`` is what makes
    the knob work uniformly: 5 of the 12 services do not declare ``LOG_LEVEL`` at all.
    """
    if level is None:
        return os.getenv("LOG_LEVEL", DEFAULT_LEVEL).upper()
    if isinstance(level, str):
        return level.upper()
    return level


def build_config(level: str | int | None = None) -> dict[str, Any]:
    """Return the ``dictConfig`` dictionary.  Exposed separately so it can be asserted on."""
    resolved = _resolve_level(level)
    return {
        "version": 1,
        # NOT cosmetic, and the one line in this file that must never be flipped:
        # ``dictConfig`` defaults this to True, which sets ``.disabled = True`` on every
        # logger created *before* the call — i.e. every ``app.*`` logger declared at module
        # level in a module imported ahead of ``app.main``.  Flipping it makes logging worse
        # than doing nothing, and it looks like success because *some* lines still appear.
        # This is not hypothetical: it was in production in account-service via alembic's
        # ``fileConfig`` (P3-58).  Guarded by test_existing_logger_survives_setup.
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": LOG_FORMAT},
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "standard",
            },
        },
        "root": {
            "handlers": ["stderr"],
            "level": resolved,
        },
        "loggers": {name: {"handlers": [], "level": resolved, "propagate": True} for name in UVICORN_LOGGERS},
    }


def setup_logging(level: str | int | None = None) -> None:
    """Configure process-wide logging.

    ``level=None`` reads ``LOG_LEVEL`` from the environment (default ``INFO``).  Idempotent:
    ``dictConfig`` *replaces* the root handler list rather than appending, so repeated calls
    leave exactly one handler.
    """
    logging.config.dictConfig(build_config(level))
