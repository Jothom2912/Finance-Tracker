"""Architecture boundary tests using pytest-archon.

Mirrors ai-service/analytics-service. Until now notification-service had no
such test, so the hexagonal rule CLAUDE.md says is enforced was in fact
unenforced here — and `app/domain/rules.py` had already drifted, importing the
RabbitMQ event contracts into the domain layer.
"""

from __future__ import annotations

from pytest_archon import archrule


def test_domain_does_not_import_adapters() -> None:
    (archrule("domain_no_adapters").match("app.domain.*").should_not_import("app.adapters.*").check("app"))


def test_domain_does_not_import_application() -> None:
    (archrule("domain_no_application").match("app.domain.*").should_not_import("app.application.*").check("app"))


def test_domain_does_not_import_infrastructure() -> None:
    """Domain takes primitives; the wire format is the application's problem.

    ``contracts`` is the inter-service RabbitMQ payload package, so it counts
    as infrastructure here even though it is pure Pydantic — a wire-format
    change must not be able to reach into domain rules.
    """
    (
        archrule("domain_no_infrastructure")
        .match("app.domain.*")
        .should_not_import("contracts.*")
        .should_not_import("sqlalchemy.*")
        .should_not_import("httpx.*")
        .should_not_import("aio_pika.*")
        .should_not_import("fastapi.*")
        .check("app")
    )


def test_ports_do_not_import_adapters() -> None:
    (archrule("ports_no_adapters").match("app.application.ports.*").should_not_import("app.adapters.*").check("app"))
