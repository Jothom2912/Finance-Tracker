import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compose_check.py"
SPEC = importlib.util.spec_from_file_location("compose_check", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
compose_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compose_check)

Service = compose_check.Service
check_k8s_parity = compose_check.check_k8s_parity
check_migration_ordering = compose_check.check_migration_ordering
MIGRATION_OWNERS = compose_check.MIGRATION_OWNERS


def _service(name: str) -> object:
    return Service(name, 1)


def test_k8s_parity_detects_missing_workload(tmp_path: Path) -> None:
    k8s = tmp_path / "k8s"
    apps = k8s / "apps"
    apps.mkdir(parents=True)
    (k8s / "kustomization.yaml").write_text("resources:\n  - apps/user-service.yaml\n", encoding="utf-8")
    (apps / "user-service.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: user-service\n",
        encoding="utf-8",
    )
    problems: list[str] = []

    required, names = check_k8s_parity(
        [_service("user-service"), _service("notification-consumer")],
        k8s / "kustomization.yaml",
        problems,
    )

    assert (required, names) == (2, 1)
    assert len(problems) == 1
    assert "notification-consumer" in problems[0]


def test_k8s_parity_accepts_alias_and_excludes_migration(tmp_path: Path) -> None:
    k8s = tmp_path / "k8s"
    infra = k8s / "infra"
    infra.mkdir(parents=True)
    (k8s / "kustomization.yaml").write_text("resources:\n  - infra/ollama-pull.yaml\n", encoding="utf-8")
    (infra / "ollama-pull.yaml").write_text(
        "apiVersion: batch/v1\nkind: Job\nmetadata:\n  name: ollama-pull-qwen3\n",
        encoding="utf-8",
    )
    problems: list[str] = []

    required, names = check_k8s_parity(
        [_service("ollama-pull"), _service("user-migration")],
        k8s / "kustomization.yaml",
        problems,
    )

    assert (required, names) == (1, 1)
    assert problems == []


def test_migration_ordering_detects_worker_without_completed_dependency() -> None:
    owner = _service("user-service")
    owner.image = "finance-tracker-user-service"
    owner.depends_on["user-migration"] = "service_completed_successfully"
    migration = _service("user-migration")
    migration.image = owner.image
    migration.command = True
    migration.depends_on["postgres"] = "service_healthy"
    worker = _service("user-outbox-worker")
    worker.image = owner.image
    problems: list[str] = []
    original = dict(MIGRATION_OWNERS)
    MIGRATION_OWNERS.clear()
    MIGRATION_OWNERS["user-service"] = "user-migration"
    try:
        checked = check_migration_ordering([owner, migration, worker], problems)
    finally:
        MIGRATION_OWNERS.clear()
        MIGRATION_OWNERS.update(original)

    assert checked == 2
    assert len(problems) == 1
    assert "user-outbox-worker" in problems[0]
