"""Architecture fitness test — read-only projection enforcement.

Certain MySQL models are *projections*: rows are written to them
only by the RabbitMQ consumers that materialise events from the
owning microservice.  Writing to them from anywhere else in the
monolith would create a split-brain with the service that owns
the aggregate.

This test detects common write patterns at the AST level.  It
doesn't try to catch *every* theoretical write (SQLAlchemy is
expressive enough that full coverage would require runtime event
listeners), but it catches the patterns a human accidentally
reaches for when they forget a model is a projection:

- Constructor calls: ``TransactionModel(...)``, ``Category(...)``,
  etc.  A constructor is almost always followed by a ``session.add``.
- Core write statements: ``insert(TransactionModel)``,
  ``update(Category)``, ``delete(PlannedTransactions)``.

Read access via ``session.query(TransactionModel)``,
``select(Category)``, attribute reads on joined rows etc. is fine
and intentionally not flagged.

Allowed write sites:
- ``backend/consumers/`` — the projection consumers themselves.
- ``backend/scripts/`` — one-off maintenance / seed scripts that
  operate outside the live request/event cycle.
- ``backend/migrations/`` — schema tooling.
- ``tests/`` — test fixtures construct models directly on purpose.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent.parent / "backend"

# Projection model classes, identified by the module they live in.
# The class *name* alone isn't enough because the domain entities
# in ``backend/category/domain/entities.py`` and elsewhere share
# names like ``Category`` with the MySQL projection.  We only want
# to flag constructor calls on symbols that were actually imported
# from ``backend.models.mysql.*``.
READ_ONLY_MODELS_BY_NAME = {
    "Transaction",
    "Category",
    "PlannedTransactions",
}
READ_ONLY_SOURCE_PREFIX = "backend.models.mysql"

ALLOWED_DIRS = {
    "consumers",  # projection consumers materialise events
    "scripts",  # seeds, one-off maintenance (outside live cycle)
    "migrations",  # alembic / neo4j / elasticsearch schema tooling
    "repositories",  # legacy sync repos kept for scripts, not API code
    "dumps",
}

# Known SQLAlchemy core-style write callables that take a Table/Model
# as their first argument: ``insert(Model)``, ``update(Model)``,
# ``delete(Model)``.  These are separate from session.add / merge /
# direct constructor calls and need their own check.
CORE_WRITE_FUNCS = {"insert", "update", "delete"}


def _iter_py_files() -> list[Path]:
    files: list[Path] = []
    for py in BACKEND_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        if set(py.parts) & ALLOWED_DIRS:
            continue
        files.append(py)
    return files


def _read_only_aliases(tree: ast.AST) -> dict[str, str]:
    """Return ``{local_name: original_name}`` for each projection
    model imported into this module from ``backend.models.mysql.*``.

    This is how we disambiguate ``Category`` the MySQL projection
    from ``Category`` the domain entity: both exist in the tree,
    but only the first is imported from models.mysql.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if not node.module or not node.module.startswith(READ_ONLY_SOURCE_PREFIX):
            continue
        for alias in node.names:
            if alias.name in READ_ONLY_MODELS_BY_NAME:
                local = alias.asname or alias.name
                aliases[local] = alias.name
    return aliases


def _find_constructor_writes(
    tree: ast.AST,
    aliases: dict[str, str],
) -> list[tuple[int, str]]:
    """Return (lineno, original_name) for every ``Model(...)`` call
    where ``Model`` resolves to a projection import.
    """
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in aliases:
            hits.append((node.lineno, aliases[func.id]))
    return hits


def _find_core_writes(
    tree: ast.AST,
    aliases: dict[str, str],
) -> list[tuple[int, str]]:
    """Return (lineno, "insert(Model)") for SQLAlchemy core-level
    write statements against read-only models.
    """
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_core_write = (isinstance(func, ast.Name) and func.id in CORE_WRITE_FUNCS) or (
            isinstance(func, ast.Attribute) and func.attr in CORE_WRITE_FUNCS
        )
        if not is_core_write:
            continue
        func_name = func.id if isinstance(func, ast.Name) else func.attr  # type: ignore[union-attr]
        for arg in node.args:
            if isinstance(arg, ast.Name) and arg.id in aliases:
                hits.append((node.lineno, f"{func_name}({aliases[arg.id]})"))
    return hits


def test_no_writes_to_read_only_projections() -> None:
    """No file outside the allowlist may construct, insert into,
    update or delete from the read-only projection models.
    """
    violations: list[str] = []
    for py_file in _iter_py_files():
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        aliases = _read_only_aliases(tree)
        if not aliases:
            continue  # file doesn't import any projection model at all

        for lineno, model in _find_constructor_writes(tree, aliases):
            rel = py_file.relative_to(BACKEND_ROOT.parent)
            violations.append(f"{rel}:{lineno}  {model}(...)  — constructor call")

        for lineno, pattern in _find_core_writes(tree, aliases):
            rel = py_file.relative_to(BACKEND_ROOT.parent)
            violations.append(f"{rel}:{lineno}  {pattern}  — core write")

    assert not violations, (
        "Read-only projection models written outside the allowlist "
        "(backend/consumers/, backend/scripts/, backend/migrations/, "
        "backend/repositories/).  If you need to persist a transaction "
        "or category, call transaction-service via HTTP instead.\n\n" + "\n".join(violations)
    )


def test_projection_markers_present() -> None:
    """Defensive: the info={"read_only": True} marker on the models
    must not silently disappear.  If someone edits the table and
    forgets to restore the flag, this test flags it.
    """
    from backend.models.mysql.category import Category
    from backend.models.mysql.planned_transactions import PlannedTransactions
    from backend.models.mysql.transaction import Transaction

    for model in (Transaction, Category, PlannedTransactions):
        info = dict(model.__table__.info or {})
        assert info.get("read_only") is True, (
            f"{model.__name__} is missing info={{'read_only': True}} — "
            "without the marker, readers can't tell they're looking at "
            "a projection.  Restore it before merging."
        )
        assert info.get("owned_by") == "transaction-service", (
            f"{model.__name__} must declare owned_by='transaction-service' "
            "so its provenance is obvious to future readers."
        )
