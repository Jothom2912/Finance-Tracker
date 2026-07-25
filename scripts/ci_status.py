"""Report the latest CI run for a branch, without needing `gh`.

Why this exists: three CI jobs were found red by accident on 2026-07-25, and
banking-service turned out to have been red since 2026-07-17 — nine days —
because nothing surfaced it. The prevention half of that problem is
`.githooks/pre-commit` (see decisions/2026-07-26-ci-feedback-loop.md); this is
the detection half.

It uses the *unauthenticated* GitHub REST API, which works because this repo is
public. Run status, per-job conclusions and per-step conclusions are all
readable that way; only the log text needs auth (403). In practice the step
name plus the annotation is enough to reproduce a failure locally, which is
better than reading the log anyway.

Set GH_TOKEN (or GITHUB_TOKEN) to lift the 60-requests/hour anonymous rate
limit, or if the repo ever goes private. Nothing else is required.

Usage::

    make ci-status                  # current branch
    python3 scripts/ci_status.py    # same
    python3 scripts/ci_status.py --branch master
    python3 scripts/ci_status.py --watch      # poll until the run finishes

Exit codes: 0 = success, 1 = failure, 2 = still running, 3 = could not tell.
Only the standard library is used, so it runs under any python3 without a venv.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"

EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_RUNNING = 2
EXIT_UNKNOWN = 3


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _repo_slug() -> str:
    """owner/name from origin, for both https and ssh remotes."""
    url = _git("remote", "get-url", "origin")
    match = re.search(r"github\.com[:/](?P<slug>[^/]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise SystemExit(f"ci-status: cannot parse a GitHub repo from origin: {url}")
    return match.group("slug")


def _get(url: str, token: str | None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "finans-tracker-ci-status",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # 403 on an anonymous request is nearly always the hourly rate limit,
        # not a permissions problem — say so rather than printing a bare 403.
        if exc.code == 403 and not token:
            raise SystemExit(
                "ci-status: GitHub returned 403. Anonymous requests are capped at\n"
                "           60/hour — set GH_TOKEN to lift it."
            ) from exc
        raise SystemExit(f"ci-status: GitHub returned {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"ci-status: cannot reach GitHub ({exc.reason})") from exc


def _latest_run(slug: str, branch: str, token: str | None) -> dict | None:
    data = _get(f"{API}/repos/{slug}/actions/runs?branch={branch}&per_page=1", token)
    runs = data.get("workflow_runs") or []
    return runs[0] if runs else None


def _report_failures(slug: str, run: dict, token: str | None) -> None:
    data = _get(f"{API}/repos/{slug}/actions/runs/{run['id']}/jobs?per_page=100", token)
    jobs = data.get("jobs", [])

    failed = [j for j in jobs if j["conclusion"] not in ("success", "skipped", None)]
    skipped = [j for j in jobs if j["conclusion"] == "skipped"]

    print(f"\n  {len(jobs) - len(failed) - len(skipped)} green · {len(failed)} failed · {len(skipped)} skipped")

    for job in failed:
        steps = [s["name"] for s in job.get("steps", []) if s["conclusion"] == "failure"]
        print(f"\n  FAILED  {job['name']}")
        for step in steps:
            print(f"          step: {step}")
        print(f"          {job['html_url']}")

    # A skipped job is not neutral here: `needs:` means one red job silently
    # switches off downstream coverage. That is how e2e stopped running for
    # nine days without anyone noticing.
    if skipped:
        print(f"\n  Skipped (downstream of a failure): {', '.join(j['name'] for j in skipped)}")


def _print_run(run: dict) -> None:
    title = run.get("display_title") or run.get("head_commit", {}).get("message", "")
    print(f"  {run['head_sha'][:8]}  {title.splitlines()[0][:60]}")
    print(f"  branch {run['head_branch']} · {run['created_at'][:16].replace('T', ' ')} · {run['html_url']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Latest CI run for a branch (no gh required).")
    parser.add_argument("--branch", help="Branch to report on (default: current)")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll every 20s until the run completes",
    )
    args = parser.parse_args()

    import os

    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    slug = _repo_slug()
    branch = args.branch or _git("rev-parse", "--abbrev-ref", "HEAD")

    while True:
        run = _latest_run(slug, branch, token)
        if run is None:
            print(f"ci-status: no runs found for branch {branch!r}")
            return EXIT_UNKNOWN

        if run["status"] != "completed":
            print(f"CI {run['status'].upper()} — {slug}")
            _print_run(run)
            if not args.watch:
                return EXIT_RUNNING
            time.sleep(20)
            continue

        conclusion = run["conclusion"]
        print(f"CI {str(conclusion).upper()} — {slug}")
        _print_run(run)
        if conclusion != "success":
            _report_failures(slug, run, token)
            return EXIT_FAILURE
        return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
