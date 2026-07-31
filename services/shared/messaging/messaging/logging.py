"""Worker logging setup — a thin shim over :mod:`observability.logging`.

Kept as its own name and signature so the 23 worker call sites are untouched by P3-57.
The configuration itself now lives in ``shared/observability``, because API processes need
the same thing and ``messaging.logging`` would be an untrue home for it — a module named
after the message bus should not be what a service imports in order to log.

The one behavioural change: ``basicConfig`` was a no-op when the root logger already had
handlers, whereas ``dictConfig`` *replaces* the handler list.  For a worker that is the same
outcome — exactly one handler on root, in the same format — but it also means a worker now
gets the intended configuration even if something configured logging before it, instead of
silently inheriting whatever was there.
"""

from __future__ import annotations

import logging

from observability.logging import LOG_FORMAT, setup_logging

__all__ = ["LOG_FORMAT", "setup_worker_logging"]


def setup_worker_logging(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure process-wide logging for a worker and return its logger."""
    setup_logging(level)
    return logging.getLogger(name)
