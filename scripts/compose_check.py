"""Build-hygiene checks: what a service *deploys* must be what we verified.

Two rules, one script, one failure mode in common — **a green run that proves
nothing**. Both regressions look like success: the build passes, the container
runs, the verification goes green, and the thing it exercised is not the thing
that ships. That shared symptom is why they live together despite reading
different files, and it is why this is a script rather than a review convention.
(The name is still ``compose_check.py`` for the wiring's sake; the scope is
build hygiene. Rule 4 reads ``services/*/`` on disk, not compose.)

Rules 1-3 come from P3-40 (per-worker image staleness), rule 4 from P2-37
(two install paths in one service), rule 6 from P2-21 (Compose/Kustomize drift).

Why rule 4 exists: budget-service's image ran ``pip install -r
requirements.txt`` (FastAPI 0.115.0) while its tests and its mypy gate read
``uv.lock`` (0.136.3). On 2026-07-27 that shipped a container which died at
import while all 117 tests and the whole typecheck gate were green — a service
cannot have two disagreeing sources of truth for one dependency. Note the
condition is *both files present*: ``account`` and ``banking`` carry only a
``requirements.txt`` and so cannot drift; they have one untruthfully-pinned
source instead of two disagreeing ones, which is P3-23/P3-01's problem, not
this one's.

Why this exists (rules 1-3): until 2026-07-27 every worker/consumer/scheduler carried its
own ``build:`` block pointing at the same Dockerfile as its API service, so
Compose built and tagged a *separate image per compose service*. The result was
not a broken system but a lying one — ``docker compose build banking-service``
left that service's four workers on whatever they were built from last, ``ps``
reported ``running``, and nothing anywhere carried a version. During the F1-05
quiet-sweep verification a scenario passed for the wrong reason because the API
had new code and the saga-command consumer had a week-old image.

That is the class of defect this file guards: not a bug in the product, a bug in
the *evidence*. It is worth a script rather than a convention because the
symptom of a regression is a green verification run, which is precisely the
thing nobody re-checks.

Same shape as ``notes_check.py`` and ``ci_status.py``: narrow scope, stdlib only
(no PyYAML — CI's ``repo-lint`` job installs ruff and nothing else), fast enough
for a pre-commit hook, and it fails loudly rather than skipping.

What it checks:

1. **Project name is pinned** — a top-level ``name:``. Without it Compose derives
   the image tags from the directory name, while the workers reference
   ``finance-tracker-<svc>`` as a literal; a clone into a differently-named
   directory would then build one tag and look up another.
2. **No worker builds** — a service with a ``command:`` override must not also
   declare ``build:``. That combination is exactly the regression: it forks a
   second image off the same Dockerfile.
3. **Every referenced tag is built** — each ``image: finance-tracker-*`` must be
   produced by exactly one service that declares ``build:``, so no worker can
   reference an image nothing in the file creates.
4. **One install path per service** — a directory under ``services/`` must not
   contain both ``uv.lock`` and ``requirements.txt``. Whichever one the
   Dockerfile reads, the other is a second answer to "what versions does this
   service run", and nothing reconciles them.
5. **The perimeter cannot drift** — ``services/frontend/nginx.conf`` is the
   security perimeter (ADR-0005, P3-43), and it was the one file nothing read.
   Five assertions: upstreams resolve to a compose service on its *container*
   port; no proxying ``/api/`` catch-all but a denying one is required;
   no ``INTERNAL_API_KEY``-guarded prefix is published; and every built
   ``finance-tracker-*`` service either has a route or stands on
   ``NOT_BROWSER_FACING`` with a reason. A location with any local
   ``add_header`` must also repeat all four server-level security headers,
   because nginx otherwise drops the inherited set for that location.
6. **Kubernetes workload parity** — every Compose API, worker and datastore must
   have a resource reachable from ``k8s/kustomization.yaml``. Name aliases are
   explicit and migration one-shots are excluded because they are deployment
   phases, not long-running workloads.

   Same shared symptom as rules 1-4, in a sharper form: three of the four
   failure modes were *measured* answering 200 during P3-43. A missing proxy
   rule falls into the SPA fallback and returns ``index.html`` with status 200,
   so "route not exposed" and "route works" are indistinguishable from the
   client. Rule 5 is where that distinction lives.

Usage::

    make compose-check
    python3 scripts/compose_check.py           # same
    python3 scripts/compose_check.py --quiet   # only print problems

Exit codes: 0 = clean, 1 = problems found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE = REPO_ROOT / "docker-compose.yml"
SERVICES = REPO_ROOT / "services"
NGINX_CONF = SERVICES / "frontend" / "nginx.conf"
KUSTOMIZATION = REPO_ROOT / "k8s" / "kustomization.yaml"

# This one root resource is deliberately gitignored; k8s-up.sh fails closed
# with instructions to create it from the tracked example. A fresh CI checkout
# must still be able to validate workload parity without inventing credentials.
KUSTOMIZE_OPTIONAL_RESOURCES = {KUSTOMIZATION.parent / "secrets.yaml"}

# Tags this repo builds itself, as opposed to `postgres:16` and friends.
LOCAL_IMAGE_PREFIX = "finance-tracker-"

TOP_LEVEL_NAME = re.compile(r"^name:\s*(\S+)\s*$")
SERVICE_NAME = re.compile(r"^  ([A-Za-z0-9._-]+):\s*$")
SERVICE_KEY = re.compile(r"^    ([A-Za-z0-9._-]+):\s*(.*)$")
PORT_ENTRY = re.compile(r"^      - (\S+)\s*$")
DEPENDENCY_NAME = re.compile(r"^      ([A-Za-z0-9._-]+):\s*$")
DEPENDENCY_CONDITION = re.compile(r"^        condition:\s*([A-Za-z0-9._-]+)\s*$")
KUSTOMIZE_RESOURCE = re.compile(r"^\s{2}-\s+([^#]+?)\s*$")
YAML_METADATA_NAME = re.compile(r"^  name:\s*([A-Za-z0-9._-]+)\s*$")

# Compose and Kubernetes use different historical names for these resources.
K8S_NAME_ALIASES = {
    "ollama-pull": "ollama-pull-qwen3",
}

# One-shot migration services are verified by the migration-ordering rule. They
# intentionally have no long-running Kubernetes workload counterpart.
K8S_PARITY_EXCLUDED_SUFFIXES = ("-migration",)

MIGRATION_OWNERS = {
    "user-service": "user-migration",
    "transaction-service": "transaction-migration",
    "account-service": "account-migration",
    "categorization-service": "categorization-migration",
    "budget-service": "budget-migration",
    "goal-service": "goal-migration",
    "banking-service": "banking-migration",
    "saga-service": "saga-migration",
    "notification-service": "notification-migration",
}


class Service:
    """The keys these checks care about, per compose service."""

    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        self.build = False
        self.command = False
        self.image: str | None = None
        # Container-side ports only (the right-hand side of a `ports:` mapping).
        # Rule 5 compares `proxy_pass` against these, and the distinction is the
        # whole point: account-service publishes 8004 but *listens* on 8003.
        self.container_ports: set[str] = set()
        self.depends_on: dict[str, str | None] = {}


def parse(text: str) -> tuple[str | None, list[Service]]:
    """Extract the project name and per-service build/command/image.

    A deliberate line parser rather than a YAML load: this must run in a job
    that installs only ruff. It relies on the file's uniform two-space
    indentation, which check 2 and 3 would flag as a false positive if it ever
    stopped holding — a loud failure, not a silent pass.
    """
    project: str | None = None
    services: list[Service] = []
    current: Service | None = None
    in_services = False
    in_ports = False
    in_depends_on = False
    current_dependency: str | None = None

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        if not line.startswith(" "):
            match = TOP_LEVEL_NAME.match(line)
            if match:
                project = match.group(1)
            in_services = line.startswith("services:")
            current = None
            in_ports = False
            in_depends_on = False
            current_dependency = None
            continue

        if not in_services:
            continue

        match = SERVICE_NAME.match(line)
        if match:
            current = Service(match.group(1), number)
            services.append(current)
            in_ports = False
            in_depends_on = False
            current_dependency = None
            continue

        if current is None:
            continue

        match = SERVICE_KEY.match(line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            in_ports = key == "ports"
            in_depends_on = key == "depends_on"
            current_dependency = None
            if key == "build":
                current.build = True
            elif key == "command":
                current.command = True
            elif key == "image":
                current.image = value
            continue

        if in_depends_on:
            match = DEPENDENCY_NAME.match(line)
            if match:
                current_dependency = match.group(1)
                current.depends_on[current_dependency] = None
                continue
            match = DEPENDENCY_CONDITION.match(line)
            if match and current_dependency is not None:
                current.depends_on[current_dependency] = match.group(1)
                continue

        if in_ports:
            match = PORT_ENTRY.match(line)
            if match:
                # "8004:8003" -> 8003; "127.0.0.1:9200:9200" -> 9200. The last
                # segment is the container port in every Compose short form.
                current.container_ports.add(match.group(1).strip('"').split(":")[-1])

    return project, services


def check(project: str | None, services: list[Service], problems: list[str]) -> None:
    if project is None:
        problems.append(
            "no top-level `name:` — image tags would be derived from the directory "
            "name while workers reference them as literals (P3-40 step 1)"
        )

    built: dict[str, list[str]] = {}
    for service in services:
        if service.build and service.image:
            built.setdefault(service.image, []).append(service.name)

    for service in services:
        if service.build and service.command:
            problems.append(
                f"{service.name} (line {service.line}): declares both `command:` and "
                "`build:` — a worker must reuse its API service's `image:`, or "
                "rebuilding that service will silently leave this one on stale code"
            )
        if service.build and not service.image:
            problems.append(
                f"{service.name} (line {service.line}): has `build:` but no explicit "
                "`image:` — the tag its workers reference must be declared, not inferred"
            )

        image = service.image
        if image and image.startswith(LOCAL_IMAGE_PREFIX) and image not in built:
            problems.append(
                f"{service.name} (line {service.line}): references `{image}`, which no service in this file builds"
            )

    for image, owners in built.items():
        if len(owners) > 1:
            problems.append(f"`{image}` is built by more than one service: {', '.join(owners)}")


def check_install_paths(problems: list[str]) -> int:
    """Rule 4: no service directory may hold both ``uv.lock`` and ``requirements.txt``.

    Returns the number of service directories inspected, so the summary line can
    report coverage — a check that silently found nothing to look at is the same
    failure as the ones it guards against.
    """
    inspected = 0
    for directory in sorted(SERVICES.iterdir()):
        if not directory.is_dir():
            continue
        inspected += 1
        lock = directory / "uv.lock"
        requirements = directory / "requirements.txt"
        if lock.is_file() and requirements.is_file():
            problems.append(
                f"services/{directory.name}: has both `uv.lock` and `requirements.txt` — "
                "two sources of truth for one dependency set. The image reads one and the "
                "tests read the other, so a green `make check` says nothing about what "
                "ships (P2-37). Delete whichever the Dockerfile does not install from."
            )
    return inspected


# Rule 5's tables. Both are deliberately data, not code: the point of the rule is
# that adding a service forces an explicit decision, and an explicit decision has
# to be writable somewhere.

# Service-to-service routes behind INTERNAL_API_KEY. Publishing one through the
# perimeter would put an S2S surface on the internet with a shared static key as
# its only guard. Each entry carries the guard's location so the claim is checkable.
INTERNAL_PREFIXES = {
    "/api/v1/internal/": "account-service/app/adapters/inbound/internal_api.py",
    "/api/v1/categorize": "categorization-service/app/adapters/inbound/categorize_api.py",
}

# Built services the browser deliberately does not talk to. A service absent from
# both nginx.conf and this list is the regression ADR-0005 point 4 names: added
# without anyone deciding whether it is public.
NOT_BROWSER_FACING = {
    "frontend": "is the perimeter itself",
    "saga-service": "browser reads sagas via gateway-service's /api/v1/sagas proxy",
    "analytics-service": "internal CQRS read store; only ai-service and gateway query it",
}

LOCATION = re.compile(r"^\s*location\s+(\S+)(?:\s+(\S+))?\s*\{")
PROXY_PASS = re.compile(r"^\s*proxy_pass\s+http://([A-Za-z0-9._-]+):(\d+)\s*;")
RETURN_CODE = re.compile(r"^\s*return\s+(\d{3})\b")
ADD_HEADER = re.compile(r"^\s*add_header\s+([^\s;]+)\b", re.IGNORECASE)

REQUIRED_SECURITY_HEADERS = (
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
)


class Location:
    """One ``location`` block, with what it does about forwarding."""

    def __init__(self, path: str, line: int, modifier: str | None) -> None:
        self.path = path
        self.line = line
        self.modifier = modifier
        self.upstreams: list[tuple[str, str]] = []
        self.returns: str | None = None
        self.headers: set[str] = set()

    @property
    def proxies(self) -> bool:
        return bool(self.upstreams)


def parse_nginx(text: str, problems: list[str]) -> list[Location]:
    """Line-parse ``location`` blocks and their ``proxy_pass``/``return``.

    Brace depth, not order, decides ownership. A location using a modifier
    (``=``, ``~``, ``^~``) is reported rather than analysed: prefix reasoning
    below would be wrong for it, and being wrong quietly is the failure this
    whole file exists to prevent.
    """
    locations: list[Location] = []
    stack: list[Location | None] = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].rstrip()
        if not line:
            continue

        match = LOCATION.match(line)
        if match:
            first, second = match.group(1), match.group(2)
            if second is None:
                location = Location(first, number, None)
            else:
                location = Location(second, number, first)
                problems.append(
                    f"nginx.conf line {number}: `location {first} {second}` uses a modifier. "
                    "Rule 5 reasons about prefix matches only, so it cannot judge this block — "
                    "it would pass without having checked anything. Express the route as a "
                    "prefix, or teach rule 5 the modifier's semantics."
                )
            locations.append(location)
            stack.append(location)
            continue

        current = stack[-1] if stack else None
        if current is not None:
            match = PROXY_PASS.search(line)
            if match:
                current.upstreams.append((match.group(1), match.group(2)))
            match = RETURN_CODE.search(line)
            if match:
                current.returns = match.group(1)
            match = ADD_HEADER.search(line)
            if match:
                current.headers.add(match.group(1).lower())

        for char in line:
            if char == "{":
                stack.append(None)
            elif char == "}" and stack:
                stack.pop()

    return locations


def check_location_security_headers(locations: list[Location], problems: list[str]) -> int:
    """Reject location-local headers that shadow the inherited security set."""
    checked = 0
    required = set(REQUIRED_SECURITY_HEADERS)
    for location in locations:
        if not location.headers:
            continue
        checked += 1
        missing = required - location.headers
        if missing:
            rendered = ", ".join(sorted(missing))
            problems.append(
                f"nginx.conf line {location.line}: `location {location.path}` has a local "
                f"`add_header`, so nginx stops inheriting the server-level security headers; "
                f"repeat the missing headers here: {rendered} (P3-47)"
            )
    return checked


def check_nginx_perimeter(services: list[Service], problems: list[str]) -> tuple[int, int]:
    """Rule 5: ``services/frontend/nginx.conf`` is the security perimeter (P3-43, ADR-0005).

    Five assertions, each with a failure mode it has been seen to fail on. Returns
    (locations parsed, proxy_pass directives verified) for the summary line.
    """
    if not NGINX_CONF.is_file():
        problems.append(
            f"{NGINX_CONF.relative_to(REPO_ROOT)} not found — the perimeter's only definition is "
            "missing, and rule 5 would otherwise report success having read nothing (P3-43)"
        )
        return 0, 0

    locations = parse_nginx(NGINX_CONF.read_text(encoding="utf-8"), problems)
    by_name = {service.name: service for service in services}
    verified = 0

    # 1. Every upstream resolves to a compose service listening on that exact
    #    container port. account-service publishes 8004 and listens on 8003;
    #    `proxy_pass http://account-service:8004` is a 502 nothing else catches.
    for location in locations:
        for host, port in location.upstreams:
            service = by_name.get(host)
            if service is None:
                problems.append(
                    f"nginx.conf line {location.line}: `location {location.path}` proxies to "
                    f"`{host}`, which is not a service in docker-compose.yml — nginx resolves "
                    "upstream names at config load, so this does not fail one route, it stops "
                    "nginx from starting at all"
                )
                continue
            if not service.container_ports:
                problems.append(
                    f"nginx.conf line {location.line}: `{host}` publishes no `ports:` in "
                    f"docker-compose.yml, so port {port} cannot be verified. Rule 5 refuses to "
                    "pass an unverifiable upstream — a skipped assertion reads like a checked one."
                )
                continue
            if port not in service.container_ports:
                published = ", ".join(sorted(service.container_ports))
                problems.append(
                    f"nginx.conf line {location.line}: `location {location.path}` proxies to "
                    f"`{host}:{port}`, but {host} listens on {published} inside the container. "
                    "Compose's left-hand port is the browser's, not the upstream's "
                    "(account-service: 8004 published, 8003 internal)."
                )
                continue
            verified += 1

    # 2. No proxying catch-all, and a denying backstop is required. ADR-0005
    #    point 2 as an executable rule. The `required` half was added after the
    #    measurement in P3-43 step 1: without it, non-allowlisted /api/ paths
    #    fall into the SPA fallback and answer 200 + index.html.
    backstop = None
    for location in locations:
        if location.path not in ("/api/", "/api/v1/"):
            continue
        if location.proxies:
            hosts = ", ".join(f"{host}:{port}" for host, port in location.upstreams)
            problems.append(
                f"nginx.conf line {location.line}: `location {location.path}` proxies to {hosts} — "
                "a catch-all publishes every route the services happen to expose, including the "
                "INTERNAL_API_KEY-guarded ones. The perimeter must be a positive allowlist "
                "(ADR-0005 point 2)."
            )
        elif location.returns is not None:
            backstop = location
    if backstop is None:
        problems.append(
            "nginx.conf: no denying `location /api/ { return 404; }` backstop. Without it a "
            "path with no allowlist entry falls through to the SPA fallback and answers "
            "200 + index.html — measured 2026-07-28 on /api/v1/internal/accounts/1/exists. "
            "A forgotten proxy rule then looks like a working one."
        )

    # 3. No location may publish an INTERNAL_API_KEY-guarded prefix — neither by
    #    naming it, nor by being a prefix of it.
    for prefix, guard in INTERNAL_PREFIXES.items():
        for location in locations:
            if not location.proxies:
                continue
            if location.path.startswith(prefix) or prefix.startswith(location.path):
                problems.append(
                    f"nginx.conf line {location.line}: `location {location.path}` publishes the "
                    f"internal route `{prefix}` (guarded by INTERNAL_API_KEY in {guard}). "
                    "A service-to-service surface behind a shared static key does not belong on "
                    "the public perimeter."
                )

    # 4. A new browser-facing service must not be able to arrive silently. Every
    #    built image either has a route or an explicit reason not to.
    proxied_hosts = {host for location in locations for host, _ in location.upstreams}
    for service in services:
        if not (service.build and service.image and service.image.startswith(LOCAL_IMAGE_PREFIX)):
            continue
        if service.name in proxied_hosts:
            if service.name in NOT_BROWSER_FACING:
                problems.append(
                    f"{service.name} is on NOT_BROWSER_FACING ('{NOT_BROWSER_FACING[service.name]}') "
                    "but nginx.conf proxies to it. One of the two is out of date; the list is a "
                    "claim about the perimeter, not a place to silence this rule."
                )
            continue
        if service.name not in NOT_BROWSER_FACING:
            problems.append(
                f"{service.name} (docker-compose.yml line {service.line}) builds "
                f"`{service.image}` but has no `location` in nginx.conf and is not on "
                "NOT_BROWSER_FACING. Decide: add a proxy rule, or add the service to that list "
                "with the reason the browser never calls it (ADR-0005 point 4). Left undecided, "
                "this fails in the browser instead of here."
            )

    # 5. nginx replaces, rather than extends, inherited add_header directives
    #    when a location declares one. A cache header must not silently remove
    #    CSP, nosniff, frame protection and referrer policy from asset responses.
    check_location_security_headers(locations, problems)

    return len(locations), verified


def collect_kustomize_names(kustomization: Path, problems: list[str]) -> set[str]:
    """Collect top-level ``metadata.name`` values reachable from a Kustomization."""
    if not kustomization.is_file():
        problems.append(f"{kustomization}: missing Kustomization entry point (P2-21)")
        return set()

    names: set[str] = set()
    in_resources = False
    for raw in kustomization.read_text(encoding="utf-8").splitlines():
        if raw and not raw.startswith(" "):
            in_resources = raw.strip() == "resources:"
            continue
        if not in_resources:
            continue
        match = KUSTOMIZE_RESOURCE.match(raw)
        if not match:
            continue
        target = (kustomization.parent / match.group(1)).resolve()
        if target.is_dir():
            nested = target / "kustomization.yaml"
            names.update(collect_kustomize_names(nested, problems))
            continue
        if target.name == "kustomization.yaml":
            names.update(collect_kustomize_names(target, problems))
            continue
        if not target.is_file() and target in KUSTOMIZE_OPTIONAL_RESOURCES:
            continue
        if not target.is_file():
            try:
                source = kustomization.relative_to(REPO_ROOT)
            except ValueError:
                source = kustomization
            problems.append(f"{source} references missing resource `{match.group(1)}`")
            continue
        for line in target.read_text(encoding="utf-8").splitlines():
            name_match = YAML_METADATA_NAME.match(line)
            if name_match:
                names.add(name_match.group(1))
    return names


def check_k8s_parity(services: list[Service], kustomization: Path, problems: list[str]) -> tuple[int, int]:
    """Rule 6: every deployable Compose workload has a Kustomize resource."""
    names = collect_kustomize_names(kustomization, problems)
    required = {
        K8S_NAME_ALIASES.get(service.name, service.name)
        for service in services
        if not service.name.endswith(K8S_PARITY_EXCLUDED_SUFFIXES)
    }
    missing = sorted(required - names)
    for name in missing:
        compose_name = next(
            (service.name for service in services if K8S_NAME_ALIASES.get(service.name, service.name) == name),
            name,
        )
        problems.append(
            f"docker-compose.yml service `{compose_name}` has no resource reachable from "
            f"k8s/kustomization.yaml (expected metadata.name `{name}`; P2-21)"
        )
    return len(required), len(names)


def check_migration_ordering(services: list[Service], problems: list[str]) -> int:
    """Rule 7: DB-backed processes wait for one explicit migration owner."""
    by_name = {service.name: service for service in services}
    checked = 0
    for owner_name, migration_name in MIGRATION_OWNERS.items():
        owner = by_name.get(owner_name)
        migration = by_name.get(migration_name)
        if owner is None or migration is None:
            problems.append(f"{owner_name}: expected one-shot `{migration_name}` migration service (P3-17)")
            continue
        if migration.image != owner.image:
            problems.append(f"{migration_name}: image `{migration.image}` differs from owner `{owner.image}`")
        if not migration.command:
            problems.append(f"{migration_name}: migration service has no command override")
        if not any(
            dependency.startswith("postgres") and condition == "service_healthy"
            for dependency, condition in migration.depends_on.items()
        ):
            problems.append(f"{migration_name}: must wait for its Postgres service to become healthy")

        for consumer in services:
            if consumer.name == migration_name or consumer.image != owner.image:
                continue
            checked += 1
            condition = consumer.depends_on.get(migration_name)
            if condition != "service_completed_successfully":
                problems.append(
                    f"{consumer.name}: uses `{owner.image}` but does not wait for "
                    f"{migration_name} with `service_completed_successfully` (P3-17)"
                )

        dockerfile = SERVICES / owner_name / "Dockerfile"
        if dockerfile.is_file() and "alembic upgrade head" in dockerfile.read_text(encoding="utf-8"):
            problems.append(f"services/{owner_name}/Dockerfile still runs migrations as an API startup side effect")
    return checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="only print problems")
    args = parser.parse_args()

    if not COMPOSE.is_file():
        print(f"compose-check: {COMPOSE} not found", file=sys.stderr)
        return 1

    if not SERVICES.is_dir():
        print(f"compose-check: {SERVICES} not found", file=sys.stderr)
        return 1

    project, services = parse(COMPOSE.read_text(encoding="utf-8"))
    problems: list[str] = []
    check(project, services, problems)
    inspected = check_install_paths(problems)
    locations, upstreams = check_nginx_perimeter(services, problems)
    k8s_required, k8s_names = check_k8s_parity(services, KUSTOMIZATION, problems)
    migration_consumers = check_migration_ordering(services, problems)

    if problems:
        print(f"compose-check: {len(problems)} problem(s)\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nWhy these rules exist: "
            "dev-notes/findings/2026-07-25-per-worker-image-staleness.md (rules 1-3), "
            "dev-notes/findings/2026-07-27-none-annotation-204-fastapi-split.md (rule 4), "
            "docs/adr/0005-nginx-as-security-perimeter.md (rule 5), "
            "dev-notes/findings/2026-07-25-k8s-manifest-drift.md (rule 6), "
            "dev-notes/findings/2026-07-25-worker-migration-ordering.md (rule 7).",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        workers = sum(1 for s in services if s.command and not s.build)
        images = len({s.image for s in services if s.build})
        print(
            f"compose-check: {len(services)} services, {images} built images, "
            f"{workers} workers sharing them; {inspected} service dirs with one install "
            f"path each; {locations} nginx locations, {upstreams} upstreams verified, "
            f"security-header inheritance guarded, "
            f"{len(NOT_BROWSER_FACING)} services explicitly not browser-facing; "
            f"{k8s_required} Compose resources represented among {k8s_names} Kubernetes names. "
            f"{migration_consumers} DB-backed processes migration-gated. No problems."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
