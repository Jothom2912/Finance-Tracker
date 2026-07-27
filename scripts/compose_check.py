"""Check docker-compose.yml for the image-sharing rule P3-40 established.

Why this exists: until 2026-07-27 every worker/consumer/scheduler carried its
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="only print problems")
    args = parser.parse_args()

    if not COMPOSE.is_file():
        print(f"compose-check: {COMPOSE} not found", file=sys.stderr)
        return 1

    project, services = parse(COMPOSE.read_text(encoding="utf-8"))
    problems: list[str] = []
    check(project, services, problems)

    if problems:
        print(f"compose-check: {len(problems)} problem(s) in docker-compose.yml\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nSee dev-notes/findings/2026-07-25-per-worker-image-staleness.md for why this rule exists.",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        workers = sum(1 for s in services if s.command and not s.build)
        images = len({s.image for s in services if s.build})
        print(
            f"compose-check: {len(services)} services, {images} built images, "
            f"{workers} workers sharing them. No problems."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
