"""Verify that the CI typecheck step gates exactly the services on the allowlist.

Why this exists: the `Typecheck (mypy)` step in `.github/workflows/ci.yml` runs
for *all* python-services — the allowlist is a conditional inside the shell body,
not a job-level `if:`. That was deliberate (a skipped step renders the same as a
passing one), but it means the step's conclusion is `success` for every service
and proves nothing about whether the gate is actually gating.

The verifiable asymmetry is in the run annotations. Non-gated services emit a
`::notice`; gated ones run mypy and emit none. Both directions have to hold:

  * a gated service *with* a notice  -> the gate is not running for it
  * a non-gated service *without* one -> the condition is wrong

This is P2-31's Kontrol C, and it is not a one-off: it has to be re-run every
time a service joins the allowlist, because both counts must move. See
`dev-notes/plans/2026-07-27-p231-static-typecheck-gate.md`.

The expected allowlist is read out of `ci.yml` rather than duplicated here. A
control that keeps its own copy of the expectation can drift from what it is
checking and still report green.

Unauthenticated GitHub REST API, like `ci_status.py` — it works because the repo
is public. One run costs ~15 requests against a 60/hour anonymous cap, which is
the binding constraint while enrolling services — set GH_TOKEN (or GITHUB_TOKEN),
or just run `gh auth login` once and the script will read the token from `gh`.

Usage::

    make verify-typecheck-gate
    python3 scripts/verify_typecheck_gate.py
    python3 scripts/verify_typecheck_gate.py --sha 0295ab98

Exit codes: 0 = the asymmetry holds, 1 = it does not, 2 = could not tell.
Only the standard library is used, so it runs under any python3 without a venv.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
STEP_NAME = "Typecheck (mypy)"
NOTICE_RE = re.compile(r"typecheck not enabled for (\S+)")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_UNKNOWN = 2

_calls = 0


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def _repo_root() -> str:
    return _git("rev-parse", "--show-toplevel")


def _repo_slug() -> str:
    url = _git("remote", "get-url", "origin")
    match = re.search(r"github\.com[:/](?P<slug>[^/]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise SystemExit(f"verify-typecheck-gate: cannot parse a GitHub repo from origin: {url}")
    return match.group("slug")


def _allowlist(root: str) -> set[str]:
    """The expected gated services, read from the workflow itself."""
    path = os.path.join(root, ".github", "workflows", "ci.yml")
    try:
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
    except OSError as exc:
        raise SystemExit(f"verify-typecheck-gate: cannot read {path} ({exc})") from exc

    match = re.search(r'TYPECHECK_SERVICES:\s*"([^"]*)"', content)
    if not match:
        # Better to stop than to check against an empty expectation, which
        # would pass trivially and report a gate that gates nothing as green.
        raise SystemExit(
            "verify-typecheck-gate: no TYPECHECK_SERVICES found in ci.yml — the check cannot know what to expect"
        )
    return set(match.group(1).split())


def _token() -> str | None:
    """GH_TOKEN, GITHUB_TOKEN, or whatever `gh` has in the keychain.

    Same fallback as ci_status.py: `gh auth login` once beats a token in a
    dotfile, and this check burns ~15 requests a run against a 60/hour cap.
    """
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        return token
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def _get(url: str, token: str | None) -> object:
    global _calls
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "finans-tracker-verify-typecheck-gate",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    _calls += 1
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and not token:
            raise SystemExit(
                "verify-typecheck-gate: GitHub returned 403. Anonymous requests are\n"
                "           capped at 60/hour and one run costs ~14 — set GH_TOKEN."
            ) from exc
        raise SystemExit(f"verify-typecheck-gate: GitHub returned {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"verify-typecheck-gate: cannot reach GitHub ({exc.reason})") from exc


def _wait_for_quota(token: str | None, need: int) -> None:
    if token:
        return
    while True:
        request = urllib.request.Request(f"{API}/rate_limit")
        with urllib.request.urlopen(request, timeout=30) as response:
            remaining = int(response.headers["x-ratelimit-remaining"])
            reset = int(response.headers["x-ratelimit-reset"])
        if remaining >= need:
            return
        wait = max(5, reset - int(time.time()) + 5)
        print(
            f"[quota] {remaining} anonymous requests left, need {need} — "
            f"waiting {wait}s for reset (set GH_TOKEN to skip this)",
            flush=True,
        )
        time.sleep(wait)


def _service_of(job_name: str) -> str:
    """`analytics-service - Python 3.11` or `job (analytics-service)` -> service."""
    match = re.search(r"\(([^)]*)\)", job_name)
    candidate = match.group(1).split(",")[0].strip() if match else re.split(r"\s+-\s+", job_name)[0].strip()
    if not candidate.endswith("-service"):
        # Do not guess. A parser that silently mislabels a job turns a real
        # asymmetry into a fake verdict in either direction — which is how the
        # first run of this check reported red against a working gate.
        raise SystemExit(
            f"verify-typecheck-gate: cannot derive a service name from job "
            f"{job_name!r} — the check would be measuring the wrong thing"
        )
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the CI typecheck gate covers exactly its allowlist (P2-31 Kontrol C)."
    )
    parser.add_argument("--sha", help="Commit to check (default: HEAD)")
    args = parser.parse_args()

    token = _token()
    root = _repo_root()
    slug = _repo_slug()
    gated = _allowlist(root)
    # GitHub's head_sha filter only matches the full 40-char form, so a short
    # sha silently finds nothing. Expand it through git rather than making the
    # caller remember — the first run of this check hit exactly that trap.
    try:
        sha = _git("rev-parse", args.sha) if args.sha else _git("rev-parse", "HEAD")
    except subprocess.CalledProcessError:
        raise SystemExit(f"verify-typecheck-gate: {args.sha!r} is not a revision git knows") from None

    _wait_for_quota(token, need=20)

    runs = _get(f"{API}/repos/{slug}/actions/runs?head_sha={sha}&per_page=10", token)
    workflow_runs = runs.get("workflow_runs") or []
    if not workflow_runs:
        print(f"verify-typecheck-gate: no run found for {sha[:8]} — is it pushed?")
        return EXIT_UNKNOWN
    run = sorted(workflow_runs, key=lambda r: r["run_number"])[-1]

    # Annotations only exist once the jobs have finished. Reading them mid-run
    # would show "no notice" for every service and score as a clean pass.
    while run["status"] != "completed":
        print(f"[run] #{run['run_number']} {run['status']} — waiting 60s", flush=True)
        time.sleep(60)
        run = _get(f"{API}/repos/{slug}/actions/runs/{run['id']}", token)

    print(f"[run]       #{run['run_number']} {run['status']}/{run['conclusion']} sha={sha[:8]}")
    print(f"            {run['html_url']}")
    print(f"[allowlist] {' '.join(sorted(gated))}   (from ci.yml)\n")

    jobs = _get(f"{API}/repos/{slug}/actions/runs/{run['id']}/jobs?per_page=100", token)["jobs"]
    typecheck_jobs = [j for j in jobs if any(s["name"] == STEP_NAME for s in j.get("steps", []))]
    if not typecheck_jobs:
        print(f"verify-typecheck-gate: no job in run #{run['run_number']} has a {STEP_NAME!r} step")
        return EXIT_UNKNOWN

    noticed: dict[str, bool] = {}
    for job in typecheck_jobs:
        annotations = _get(f"{API}/repos/{slug}/check-runs/{job['id']}/annotations", token)
        hits = [a for a in annotations if NOTICE_RE.search(a.get("message") or "")]
        service = _service_of(job["name"])
        noticed[service] = bool(hits)
        print(f"  {service:26} notice={'yes' if hits else 'no ':<3}  expected={'no ' if service in gated else 'yes'}")

    seen_gated = {s for s in noticed if s in gated}
    problems = [
        f"{s} is on the allowlist but emitted a ::notice → mypy did not run for it"
        for s in sorted(seen_gated)
        if noticed[s]
    ] + [
        f"{s} is not on the allowlist but emitted no ::notice → the condition is wrong"
        for s in sorted(set(noticed) - gated)
        if not noticed[s]
    ]
    missing = gated - set(noticed)
    if missing:
        problems.append(f"allowlisted but absent from the run: {' '.join(sorted(missing))}")

    print(f"\n{len(seen_gated)} gated / {len(noticed) - len(seen_gated)} not gated   [{_calls} API requests]")

    if problems:
        print("\nTYPECHECK GATE: FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return EXIT_FAILED

    print("\nTYPECHECK GATE: OK — the asymmetry holds in both directions")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
