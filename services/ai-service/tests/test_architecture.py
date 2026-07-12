"""Architecture boundary tests using pytest-archon + port conformance.

Enforces hexagonal architecture rules:
- Domain layer has zero dependencies on infrastructure
- Ports define interfaces without knowing about adapters
- Adapters depend inward (domain + ports), never outward
- Adapters structurally satisfy the port Protocols they implement (the ports
  were decorative and signature-drifted once — audit 2026-07-07; the
  runtime_checkable isinstance checks plus the dispatcher being typed against
  the ports keep them honest and give AI-20 its adapter-swap seam)
"""

from __future__ import annotations

import inspect

from pytest_archon import archrule


def test_domain_does_not_import_adapters() -> None:
    (archrule("domain_no_adapters").match("app.domain.*").should_not_import("app.adapters.*").check("app"))


def test_domain_does_not_import_application() -> None:
    (archrule("domain_no_application").match("app.domain.*").should_not_import("app.application.*").check("app"))


def test_ports_do_not_import_adapters() -> None:
    (archrule("ports_no_adapters").match("app.application.ports.*").should_not_import("app.adapters.*").check("app"))


def test_adapters_conform_to_ports() -> None:
    from app.adapters.outbound.analytics_client import AnalyticsClient
    from app.adapters.outbound.chromadb_search import ChromaDBSearch
    from app.adapters.outbound.ollama_responder import OllamaResponder
    from app.adapters.outbound.ollama_router import OllamaRouter
    from app.application.ports.analytics_port import IAnalyticsPort
    from app.application.ports.llm_port import IResponderPort, IRouterPort
    from app.application.ports.semantic_search_port import ISemanticSearchPort

    assert isinstance(AnalyticsClient(token="t", account_id=1), IAnalyticsPort)
    assert isinstance(ChromaDBSearch(user_id=1), ISemanticSearchPort)
    assert isinstance(OllamaRouter(), IRouterPort)
    assert isinstance(OllamaResponder(), IResponderPort)


def test_port_and_adapter_method_signatures_match() -> None:
    """runtime_checkable only checks attribute presence — pin the parameters too."""
    from app.adapters.outbound.analytics_client import AnalyticsClient
    from app.adapters.outbound.chromadb_search import ChromaDBSearch
    from app.application.ports.analytics_port import IAnalyticsPort
    from app.application.ports.semantic_search_port import ISemanticSearchPort

    pairs = [
        (IAnalyticsPort, AnalyticsClient, "get_largest_expenses"),
        (IAnalyticsPort, AnalyticsClient, "get_category_breakdown"),
        (IAnalyticsPort, AnalyticsClient, "get_budget_status"),
        (ISemanticSearchPort, ChromaDBSearch, "search"),
    ]
    for port, adapter, method in pairs:
        port_params = list(inspect.signature(getattr(port, method)).parameters)
        adapter_params = list(inspect.signature(getattr(adapter, method)).parameters)
        assert port_params == adapter_params, (
            f"{adapter.__name__}.{method} drifted from {port.__name__}: {adapter_params} != {port_params}"
        )
