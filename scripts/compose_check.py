"""Build-hygiene checks: what a service *deploys* must be what we verified.

Two rules, one script, one failure mode in common — **a green run that proves
nothing**. Both regressions look like success: the build passes, the container
runs, the verification goes green, and the thing it exercised is not the thing
that ships. That shared symptom is why they live together despite reading
different files, and it is why this is a script rather than a review convention.
(The name is still ``compose_check.py`` for the wiring's sake; the scope is
build hygiene. Rule 4 reads ``services/*/`` on disk, not compose.)

Rules 1-3 come from P3-40 (per-worker image staleness), rule 4 from P2-37
(two install paths in one service).

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

# Tags this repo builds itself, as opposed to `postgres:16` and friends.
LOCAL_IMAGE_PREFIX = "finance-tracker-"

TOP_LEVEL_NAME = re.compile(r"^name:\s*(\S+)\s*$")
SERVICE_NAME = re.compile(r"^  ([A-Za-z0-9._-]+):\s*$")
SERVICE_KEY = re.compile(r"^    ([A-Za-z0-9._-]+):\s*(.*)$")


class Service:
    """The three keys this check cares about, per compose service."""

    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line
        self.build = False
        self.command = False
        self.image: str | None = None


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
            continue

        if not in_services:
            continue

        match = SERVICE_NAME.match(line)
        if match:
            current = Service(match.group(1), number)
            services.append(current)
            continue

        if current is None:
            continue

        match = SERVICE_KEY.match(line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            if key == "build":
                current.build = True
            elif key == "command":
                current.command = True
            elif key == "image":
                current.image = value

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

    if problems:
        print(f"compose-check: {len(problems)} problem(s)\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nWhy these rules exist: "
            "dev-notes/findings/2026-07-25-per-worker-image-staleness.md (rules 1-3), "
            "dev-notes/findings/2026-07-27-none-annotation-204-fastapi-split.md (rule 4).",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        workers = sum(1 for s in services if s.command and not s.build)
        images = len({s.image for s in services if s.build})
        print(
            f"compose-check: {len(services)} services, {images} built images, "
            f"{workers} workers sharing them; {inspected} service dirs with one install "
            f"path each. No problems."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
