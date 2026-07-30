"""Tests for the shared logging configuration.

The first test is the important one: it guards the ``disable_existing_loggers`` trap that was
live in production (P3-58).  The others pin the properties the P3-57 plan promises.
"""

from __future__ import annotations

import io
import logging
import re

import pytest
from observability import LOG_FORMAT, UVICORN_LOGGERS, build_config, setup_logging


@pytest.fixture(autouse=True)
def _restore_logging():
    """Save and restore global logging state so tests cannot leak into each other."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    saved_disabled = {
        name: logging.getLogger(name).disabled for name in (*UVICORN_LOGGERS, "app.pre_existing", "app.probe")
    }
    yield
    root.handlers[:] = saved_handlers
    root.level = saved_level
    for name, disabled in saved_disabled.items():
        logging.getLogger(name).disabled = disabled


def test_existing_logger_survives_setup():
    """A logger created *before* setup_logging must still emit afterwards.

    This is the regression test for the trap, not a nicety.  ``dictConfig`` defaults
    ``disable_existing_loggers`` to True, which would silence every ``app.*`` logger declared
    at module level in a module imported ahead of ``app.main`` — and the failure is invisible,
    because uvicorn's own lines keep coming.  Mutate the flag in
    ``observability/logging.py`` and this test must go red.
    """
    pre_existing = logging.getLogger("app.pre_existing")

    setup_logging("INFO")

    assert pre_existing.disabled is False
    assert pre_existing.isEnabledFor(logging.INFO)


def test_app_logger_reaches_root_with_full_format():
    """``app.*`` gets INFO through, formatted with level, timestamp and logger name."""
    setup_logging("INFO")

    logger = logging.getLogger("app.probe")
    assert logger.isEnabledFor(logging.INFO), "info must not die on the level check"

    # Assert on the configured formatter rather than on captured stderr: pytest installs its
    # own log capture, so a capsys-based assertion would test pytest's plumbing, not ours.
    (handler,) = logging.getLogger().handlers
    record = logger.makeRecord("app.probe", logging.WARNING, __file__, 1, "probe-besked", None, None)
    line = handler.formatter.format(record)

    assert "WARNING" in line, "level must be on the line — grep WARNING is the point"
    assert "[app.probe]" in line, "logger name must be on the line"
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} ", line), (
        f"expected a millisecond-precision timestamp first, got: {line!r}"
    )
    assert line.endswith("probe-besked")


def test_uvicorn_loggers_propagate_to_our_handler():
    """uvicorn's three loggers must carry our formatter, not their own.

    Without this, access lines keep uvicorn's ``INFO:     ...`` shape and stay un-greppable
    by level — and access lines are the only behavioural signal that exists in all 12
    services, since 5 of them log nothing in the request path (P3-59).
    """
    setup_logging("INFO")

    for name in UVICORN_LOGGERS:
        logger = logging.getLogger(name)
        assert logger.handlers == [], f"{name} must not keep a handler of its own"
        assert logger.propagate is True, f"{name} must propagate to root"


def test_uvicorn_access_record_lands_on_root_handler():
    """End-to-end within the process: an emitted uvicorn.access record hits our stream."""
    setup_logging("INFO")
    stream = io.StringIO()
    (handler,) = logging.getLogger().handlers
    handler.setStream(stream)

    logging.getLogger("uvicorn.access").info('%s - "%s" %s', "1.2.3.4", "GET /health", 200)

    line = stream.getvalue()
    assert "INFO" in line
    assert "[uvicorn.access]" in line
    assert "GET /health" in line


def test_setup_is_idempotent():
    """Repeated calls leave exactly one handler — dictConfig replaces, it does not append."""
    setup_logging("INFO")
    setup_logging("INFO")
    setup_logging("DEBUG")

    assert len(logging.getLogger().handlers) == 1


def test_level_resolution(monkeypatch):
    """Explicit level wins; None falls back to LOG_LEVEL; the fallback is case-insensitive."""
    # delenv, so the default assertion does not quietly depend on the developer's shell.
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert build_config("warning")["root"]["level"] == "WARNING"
    assert build_config(logging.DEBUG)["root"]["level"] == logging.DEBUG
    assert build_config()["root"]["level"] == "INFO"


def test_level_resolution_reads_environment(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    assert build_config()["root"]["level"] == "DEBUG"


def test_format_is_unchanged_from_the_worker_copies():
    """The 23 worker call sites have always used this format; pipelines parse it."""
    assert LOG_FORMAT == "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    assert build_config()["formatters"]["standard"]["format"] == LOG_FORMAT
    assert "datefmt" not in build_config()["formatters"]["standard"], (
        "no datefmt: the default keeps millisecond precision in asctime"
    )
