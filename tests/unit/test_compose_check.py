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
check_location_security_headers = compose_check.check_location_security_headers
check_build_context_hygiene = compose_check.check_build_context_hygiene
parse_nginx = compose_check.parse_nginx
MIGRATION_OWNERS = compose_check.MIGRATION_OWNERS


def _service(name: str) -> object:
    return Service(name, 1)


def _header_problems(config: str) -> list[str]:
    problems: list[str] = []
    locations = parse_nginx(config, problems)
    check_location_security_headers(locations, problems)
    return problems


def test_location_without_local_headers_inherits_security_set() -> None:
    config = """
server {
    add_header Content-Security-Policy "default-src 'self'" always;
    location /assets/ {
        try_files $uri =404;
    }
}
"""

    assert _header_problems(config) == []


def test_location_cache_header_requires_repeated_security_set() -> None:
    config = """
server {
    location /assets/ {
        add_header Cache-Control "public, immutable";
    }
}
"""

    problems = _header_problems(config)

    assert len(problems) == 1
    assert "location /assets/" in problems[0]
    for header in compose_check.REQUIRED_SECURITY_HEADERS:
        assert header in problems[0]


def test_location_accepts_cache_header_with_complete_security_set() -> None:
    config = """
server {
    location /assets/ {
        add_header Cache-Control "public, immutable";
        add_header Content-Security-Policy "default-src 'self'" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "DENY" always;
        add_header Referrer-Policy "no-referrer" always;
    }
}
"""

    assert _header_problems(config) == []


def test_build_context_hygiene_detects_missing_ignore_pattern(tmp_path: Path) -> None:
    services = tmp_path / "services"
    service = services / "example-service"
    service.mkdir(parents=True)
    (service / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text(
        ".git\n.env\n.env.*\n!.env.example\n**/.env\n**/node_modules\n*.pem\n*.key\n",
        encoding="utf-8",
    )
    problems: list[str] = []

    _, uv_dockerfiles = check_build_context_hygiene(dockerignore, services, problems)

    assert uv_dockerfiles == 0
    assert len(problems) == 1
    assert "**/.venv" in problems[0]


def test_build_context_hygiene_detects_uv_cache_retention(tmp_path: Path) -> None:
    services = tmp_path / "services"
    service = services / "example-service"
    service.mkdir(parents=True)
    (service / "Dockerfile").write_text("FROM python:3.11\nRUN uv sync --frozen\n", encoding="utf-8")
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text(
        ".git\n.env\n.env.*\n!.env.example\n**/.env\n**/.venv\n**/node_modules\n*.pem\n*.key\n",
        encoding="utf-8",
    )
    problems: list[str] = []

    _, uv_dockerfiles = check_build_context_hygiene(dockerignore, services, problems)

    assert uv_dockerfiles == 1
    assert len(problems) == 1
    assert "UV_NO_CACHE=1" in problems[0]


def test_build_context_hygiene_accepts_guarded_uv_build(tmp_path: Path) -> None:
    services = tmp_path / "services"
    service = services / "example-service"
    service.mkdir(parents=True)
    (service / "Dockerfile").write_text("FROM python:3.11\nENV UV_NO_CACHE=1\nRUN uv sync --frozen\n", encoding="utf-8")
    dockerignore = tmp_path / ".dockerignore"
    dockerignore.write_text(
        ".git\n.env\n.env.*\n!.env.example\n**/.env\n**/.venv\n**/node_modules\n*.pem\n*.key\n",
        encoding="utf-8",
    )
    problems: list[str] = []

    patterns, uv_dockerfiles = check_build_context_hygiene(dockerignore, services, problems)

    assert patterns == 9
    assert uv_dockerfiles == 1
    assert problems == []


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


def test_k8s_parity_allows_only_the_explicitly_optional_secret(tmp_path: Path) -> None:
    k8s = tmp_path / "k8s"
    k8s.mkdir()
    kustomization = k8s / "kustomization.yaml"
    kustomization.write_text(
        "resources:\n  - secrets.yaml\n  - missing-app.yaml\n",
        encoding="utf-8",
    )
    problems: list[str] = []
    optional = k8s / "secrets.yaml"
    compose_check.KUSTOMIZE_OPTIONAL_RESOURCES.add(optional)
    try:
        required, names = check_k8s_parity([], kustomization, problems)
    finally:
        compose_check.KUSTOMIZE_OPTIONAL_RESOURCES.remove(optional)

    assert (required, names) == (0, 0)
    assert len(problems) == 1
    assert "missing-app.yaml" in problems[0]


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
