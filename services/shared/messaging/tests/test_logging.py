from __future__ import annotations

import logging

from messaging.logging import LOG_FORMAT, setup_worker_logging


def test_setup_returns_named_logger() -> None:
    logger = setup_worker_logging("test.worker")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test.worker"


def test_setup_is_idempotent() -> None:
    setup_worker_logging("a")
    handler_count = len(logging.getLogger().handlers)
    setup_worker_logging("b")
    assert len(logging.getLogger().handlers) == handler_count


def test_format_matches_legacy_copies() -> None:
    assert LOG_FORMAT == "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
