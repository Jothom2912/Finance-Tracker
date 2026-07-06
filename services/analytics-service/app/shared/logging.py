from __future__ import annotations

import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from app.domain.exceptions import AnalyticsDomainError

logger = logging.getLogger("analytics.usecase")

P = ParamSpec("P")
T = TypeVar("T")


def execute_with_logging(
    use_case: str,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Konsistent use case-logging: varighed, domain-fejl som WARNING,
    uventede fejl som ERROR. Fejl re-raises altid — mapping til HTTP
    sker i adapter-laget."""

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
            except AnalyticsDomainError as exc:
                logger.warning(
                    "use_case=%s outcome=domain_error error=%s duration_ms=%.1f",
                    use_case,
                    exc,
                    (time.perf_counter() - start) * 1000,
                )
                raise
            except Exception:
                logger.error(
                    "use_case=%s outcome=error duration_ms=%.1f",
                    use_case,
                    (time.perf_counter() - start) * 1000,
                    exc_info=True,
                )
                raise
            logger.info(
                "use_case=%s outcome=ok duration_ms=%.1f",
                use_case,
                (time.perf_counter() - start) * 1000,
            )
            return result

        return wrapper

    return decorator
