#!/usr/bin/env python3
"""Fail if any compose container is dead, exited nonzero, or in a restart loop.

Why this exists (P2-38 / P2-42): CI had no way to *report* a container that
never came up.  `Wait for system` polls the 12 HTTP services, but 26 of the 53
compose services are workers with no HTTP surface at all — a port probe is not
"missing" for them, it is structurally impossible.  Their only observable
liveness signal is container state, which nothing read.  A worker could crash on
import every single run and the E2E job stayed green, because the tests it
guards do not touch that worker's queue.

Deliberately NOT in the predicate: `Health: unhealthy`.  The HTTP services are
already gated by `Wait for system`, and adding it here would make the same
failure red twice while risking a new class of flake on slow-starting
healthchecks.  This script answers one question: is the container alive?

The trap this predicate is written around
----------------------------------------
`ollama-pull` is `restart: "no"` and exits **0** once it has pulled qwen3:4b and
bge-m3 (docker-compose.yml).  It is `exited` on every correct stack.  So the
predicate must be *nonzero exit*, never *not running* — the latter would be red
on a healthy system from the first run, which is precisely the "gate that proves
nothing" failure class this item closes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass

# `restarting` is a container caught mid restart-loop, and it is NOT redundant
# with the nonzero-exit check below — it is the branch that actually fires.
# Measured: 25 of the 53 services are `restart: on-failure` and 14 are
# `unless-stopped`, so a worker that crashes on import cycles here forever rather
# than settling into `exited`.  When the control for this gate broke
# `saga-timeout-worker` with an unreachable DATABASE_URL, compose reported
# `State: restarting` with `ExitCode: 0` — so an "exited nonzero"-only predicate
# would have been blind to exactly the failure this gate is written for.
BROKEN_STATES = ("dead", "restarting")


@dataclass(frozen=True)
class Container:
    service: str
    name: str
    state: str
    exit_code: int

    @property
    def problem(self) -> str | None:
        if self.state in BROKEN_STATES:
            return f"state={self.state}"
        if self.state == "exited" and self.exit_code != 0:
            return f"exited with code {self.exit_code}"
        return None


def read_containers() -> list[Container]:
    # --all so exited containers are visible at all; the default hides them,
    # which is how a dead worker stayed invisible.
    proc = subprocess.run(
        ["docker", "compose", "ps", "--all", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(
            f"compose-state-check: `docker compose ps` failed (rc={proc.returncode}): {proc.stderr.strip()}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    containers = []
    # Compose emits JSON *lines*, not a JSON array.
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        containers.append(
            Container(
                service=row.get("Service", "?"),
                name=row.get("Name", "?"),
                state=row.get("State", "?"),
                exit_code=int(row.get("ExitCode", 0) or 0),
            )
        )
    return containers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    containers = read_containers()
    if not containers:
        print(
            "compose-state-check: no containers found — the stack is not up, which cannot be reported as success.",
            file=sys.stderr,
        )
        return 1

    broken = [(c, p) for c in containers if (p := c.problem) is not None]

    if broken:
        print(
            f"compose-state-check: {len(broken)} of {len(containers)} containers are not alive:",
            file=sys.stderr,
        )
        for container, problem in broken:
            # Name the container: "a container died" is not actionable, and the
            # whole point of the gate is a log line someone can act on.
            print(f"  {container.service} ({container.name}): {problem}", file=sys.stderr)
        print(
            "\nRead that container's logs with `docker compose logs <service>`. "
            "Why this gate exists: dev-notes/findings/2026-07-28-banking-service-dead-in-ci.md",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        expected_exited = [c.service for c in containers if c.state == "exited"]
        print(
            f"compose-state-check: {len(containers)} containers, none dead, exited "
            f"nonzero, or restarting. Exited cleanly (expected): "
            f"{', '.join(sorted(expected_exited)) or 'none'}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
