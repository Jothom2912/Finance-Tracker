"""
Architecture fitness tests — import boundary enforcement.

These tests verify that hexagonal architecture boundaries are respected:
- Bounded contexts must not import from legacy backend.repositories.*
- Application layers must not import infrastructure concerns
- Auth must not couple to legacy repository stack

Tests are initially xfail-marked and unlocked PR-by-PR.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

BOUNDED_CONTEXTS = [
    "transaction",
    "category",
    "budget",
    "analytics",
    "account",
    "goal",
    "user",
    "monthly_budget",
]

BACKEND_ROOT = Path(__file__).parent.parent.parent


def get_imports_from_file(filepath: str) -> list[str]:
    """Parse a Python file and return all import module strings."""
    with open(filepath, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
    return imports


def test_no_legacy_repo_imports_in_hex_contexts() -> None:
    """No hex bounded context may import from backend.repositories.*"""
    violations: list[str] = []
    for ctx in BOUNDED_CONTEXTS:
        ctx_path = BACKEND_ROOT / ctx
        if not ctx_path.exists():
            continue
        for py_file in ctx_path.rglob("*.py"):
            for imp in get_imports_from_file(str(py_file)):
                if imp.startswith("backend.repositories"):
                    violations.append(f"{py_file}: {imp}")
    assert not violations, (
        "Legacy repo imports in hex contexts:\n" + "\n".join(violations)
    )


def test_application_layer_no_infra_imports() -> None:
    """application/ must not import from adapters/ or models/"""
    violations: list[str] = []
    for ctx in BOUNDED_CONTEXTS:
        app_path = BACKEND_ROOT / ctx / "application"
        if not app_path.exists():
            continue
        for py_file in app_path.rglob("*.py"):
            for imp in get_imports_from_file(str(py_file)):
                if any(
                    x in imp
                    for x in [
                        "adapters",
                        "backend.models.mysql",
                        "backend.database",
                        "sqlalchemy",
                    ]
                ):
                    violations.append(f"{py_file}: {imp}")
    assert not violations, (
        "Infra imports in application layer:\n" + "\n".join(violations)
    )


def test_auth_no_legacy_repos() -> None:
    """auth.py must not import from backend.repositories"""
    auth_file = BACKEND_ROOT / "auth.py"
    imports = get_imports_from_file(str(auth_file))
    violations = [i for i in imports if i.startswith("backend.repositories")]
    assert not violations, (
        "Legacy repo imports in auth.py:\n" + "\n".join(violations)
    )
