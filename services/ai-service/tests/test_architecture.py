"""Architecture boundary tests using pytest-archon.

Enforces hexagonal architecture rules:
- Domain layer has zero dependencies on infrastructure
- Ports define interfaces without knowing about adapters
- Adapters depend inward (domain + ports), never outward
"""

from __future__ import annotations

from pytest_archon import archrule


def test_domain_does_not_import_adapters() -> None:
    (archrule("domain_no_adapters").match("app.domain.*").should_not_import("app.adapters.*").check("app"))


def test_domain_does_not_import_application() -> None:
    (archrule("domain_no_application").match("app.domain.*").should_not_import("app.application.*").check("app"))


def test_ports_do_not_import_adapters() -> None:
    (archrule("ports_no_adapters").match("app.application.ports.*").should_not_import("app.adapters.*").check("app"))
