"""Check dev-notes/ for the drift that manual upkeep always produces.

Why this exists: on 2026-07-27 a review of the vault found two files that had
never been added to `00-INDEX.md` — including an *open* MEDIUM finding, which
means it was invisible to anyone treating the index as the map — plus a
0-byte `services.md` and a `dev-notes` skill instructing agents to update
`architecture/event-catalog.md`, a file that does not exist. None of those are
mistakes anyone would repeat deliberately; they are what happens when the only
thing keeping an index honest is remembering to edit it.

Same shape as `.githooks/pre-commit` and `scripts/ci_status.py`: narrow scope,
stdlib only, fast enough to run before every commit, and it fails loudly rather
than skipping when something is missing.

What it checks:

1. **Index coverage** — every Markdown file under `dev-notes/` is referenced by
   an index (`00-INDEX.md`, or `sessions/00-SESSIONS.md` for session logs).
2. **Link integrity** — every relative Markdown link inside `dev-notes/`
   resolves to a file that exists.
3. **Frontmatter** — findings/plans/decisions carry the fields that are queried
   (`title`, `date`, `status`, plus `severity` for findings), `status` holds a
   known value, and `date` matches the filename's date prefix.
4. **Empty files** — a tracked 0-byte note is never intentional.
5. **Resolved-without-a-pointer** — a finding marked `resolved` must say what
   resolved it, since the whole point of keeping it is the trail.
6. **Retrieval budgets** — STATUS and index hooks stay bounded, so the files
   every agent reads first cannot become release-history archives again.
7. **Canonical metadata and skills** — plans use `backlog:` and Claude
   compatibility entries resolve to the canonical `.agents/skills` folders.

Usage::

    make notes-check
    python3 scripts/notes_check.py           # same
    python3 scripts/notes_check.py --quiet   # only print problems

Exit codes: 0 = clean, 1 = problems found.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTES = REPO_ROOT / "dev-notes"

# Files that are indexes or scaffolding, not indexed content.
NOT_INDEXED = {"00-INDEX.md", "README.md", "STATUS.md", "sessions/00-SESSIONS.md"}
SKIP_DIRS = {"templates", ".obsidian"}

# Which index is allowed to cover which folder. Session logs are numerous and
# write-mostly, so they live in their own index to keep 00-INDEX.md loadable.
INDEX_FOR = {"sessions": "sessions/00-SESSIONS.md"}
DEFAULT_INDEX = "00-INDEX.md"

VALID_STATUS = {
    "open",
    "in-progress",
    "done",
    "resolved",
    "superseded",
    "wont-do",
    "wont-fix",
    "accepted",
    "proposed",
}
REQUIRED_FIELDS = {
    "findings": ("title", "date", "severity", "status"),
    "plans": ("title", "date", "status"),
    "decisions": ("title", "date", "status"),
}

DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
# Markdown links, minus the ![]() image form and anything with a scheme.
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)
# Code spans and fenced blocks are stripped before looking for links: the README
# documents the link convention as `[text](relative/path.md)`, which is prose
# about links, not a link.
CODE = re.compile(r"```.*?```|`[^`]*`", re.DOTALL)
STATUS_MAX_LINES = 100
STATUS_MAX_WORDS = 1_200
INDEX_HOOK_MAX_CHARS = 240
REPO_SKILLS = ("dev-notes", "dev-notes-plan", "dev-notes-decision")


def notes_files() -> list[Path]:
    """Every Markdown file in the vault that counts as indexable content."""
    out = []
    for path in sorted(NOTES.rglob("*.md")):
        rel = path.relative_to(NOTES)
        if set(rel.parts) & SKIP_DIRS:
            continue
        out.append(path)
    return out


def parse_frontmatter(text: str) -> dict[str, str]:
    """Top-level `key: value` pairs only — enough for the fields we query.

    Deliberately not YAML: the stdlib has no YAML parser, and requiring PyYAML
    would make this check skippable on a fresh clone, which is the failure mode
    it exists to prevent.
    """
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def check_index_coverage(files: list[Path], problems: list[str]) -> None:
    index_text: dict[str, str] = {}
    for name in {DEFAULT_INDEX, *INDEX_FOR.values()}:
        path = NOTES / name
        index_text[name] = path.read_text(encoding="utf-8") if path.exists() else ""

    for path in files:
        rel = path.relative_to(NOTES).as_posix()
        if rel in NOT_INDEXED:
            continue
        top = rel.split("/")[0]
        expected = INDEX_FOR.get(top, DEFAULT_INDEX)
        # Accept a mention in the expected index, or in 00-INDEX.md as a
        # fallback so this does not fail during a reorganisation.
        if rel in index_text.get(expected, "") or rel in index_text[DEFAULT_INDEX]:
            continue
        problems.append(f"{rel}: not listed in {expected}")


def check_links(files: list[Path], problems: list[str]) -> None:
    for path in files:
        rel = path.relative_to(NOTES).as_posix()
        prose = CODE.sub("", path.read_text(encoding="utf-8"))
        for target in LINK.findall(prose):
            target = target.split("#")[0].strip()
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (path.parent / target).resolve().exists():
                problems.append(f"{rel}: dead link -> {target}")


def check_frontmatter(files: list[Path], problems: list[str]) -> None:
    for path in files:
        rel = path.relative_to(NOTES).as_posix()
        top = rel.split("/")[0]
        required = REQUIRED_FIELDS.get(top)
        if required is None:
            continue

        fields = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fields:
            problems.append(f"{rel}: no frontmatter block")
            continue
        for field in required:
            if field not in fields:
                problems.append(f"{rel}: frontmatter missing '{field}'")

        if top == "plans":
            if "backlog-items" in fields:
                problems.append(f"{rel}: use canonical 'backlog:' instead of 'backlog-items:'")
            if "backlog" not in fields:
                problems.append(f"{rel}: frontmatter missing 'backlog'")

        status = fields.get("status", "").split("#")[0].strip()
        if status and status not in VALID_STATUS:
            problems.append(f"{rel}: unknown status '{status}'")

        # A resolved finding with no pointer is a dead end for the next reader.
        if top == "findings" and status == "resolved":
            resolved_by = fields.get("resolved-by", "").split("#")[0].strip()
            if not resolved_by or resolved_by == "null":
                problems.append(f"{rel}: status resolved but resolved-by is empty")

        # The date in the frontmatter and the one in the filename must agree —
        # they drift when a file is copied from an older one as a template.
        prefix = DATE_PREFIX.match(path.name)
        if prefix:
            declared = fields.get("date", "").split()[0] if fields.get("date") else ""
            if declared and declared != prefix.group(1):
                problems.append(f"{rel}: frontmatter date {declared} != filename date {prefix.group(1)}")


def check_empty(files: list[Path], problems: list[str]) -> None:
    for path in files:
        if path.stat().st_size == 0:
            problems.append(f"{path.relative_to(NOTES).as_posix()}: empty file")


def check_retrieval_budgets(problems: list[str]) -> None:
    status = NOTES / "STATUS.md"
    status_text = status.read_text(encoding="utf-8")
    line_count = len(status_text.splitlines())
    word_count = len(status_text.split())
    if line_count > STATUS_MAX_LINES:
        problems.append(
            f"STATUS.md: {line_count} lines exceeds {STATUS_MAX_LINES}; move history to plan Outcome/session owners"
        )
    if word_count > STATUS_MAX_WORDS:
        problems.append(f"STATUS.md: {word_count} words exceeds {STATUS_MAX_WORDS}; keep only current routing context")

    index = NOTES / DEFAULT_INDEX
    lines = index.read_text(encoding="utf-8").splitlines()
    previous_was_hook = False
    for number, line in enumerate(lines, start=1):
        is_hook = line.startswith("- [")
        if is_hook and len(line) > INDEX_HOOK_MAX_CHARS:
            problems.append(f"00-INDEX.md:{number}: hook is {len(line)} characters; limit is {INDEX_HOOK_MAX_CHARS}")
        if previous_was_hook and line.startswith((" ", "\t")):
            problems.append(
                f"00-INDEX.md:{number}: continuation makes the previous hook multiline; keep one physical line"
            )
        previous_was_hook = is_hook

    backlog_lines = (NOTES / "backlog" / "BACKLOG.md").read_text(encoding="utf-8").splitlines()
    previous_was_row = False
    for number, line in enumerate(backlog_lines, start=1):
        is_row = bool(re.match(r"^\| (?:P[123]|F[123]|AI|ML)-\d+", line))
        if is_row and line.count("|") < 6:
            problems.append(
                f"backlog/BACKLOG.md:{number}: malformed work-item row; keep every field on one physical table line"
            )
        if previous_was_row and line.startswith((" ", "\t")):
            problems.append(
                f"backlog/BACKLOG.md:{number}: work-item row continues on another line; move detail below Item details"
            )
        previous_was_row = is_row


def check_skill_canonicalization(problems: list[str]) -> None:
    canonical_root = REPO_ROOT / ".agents" / "skills"
    compatibility_root = REPO_ROOT / ".claude" / "skills"
    for name in REPO_SKILLS:
        canonical = canonical_root / name / "SKILL.md"
        compatibility = compatibility_root / name / "SKILL.md"
        if not canonical.is_file():
            problems.append(f".agents/skills/{name}/SKILL.md: canonical skill missing")
            continue
        if not compatibility.is_file():
            problems.append(f".claude/skills/{name}: Claude compatibility link/file missing")
            continue
        if canonical.read_bytes() != compatibility.read_bytes():
            problems.append(f".claude/skills/{name}: stale duplicate; point it at .agents/skills/{name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="only print problems")
    args = parser.parse_args()

    if not NOTES.is_dir():
        print(f"notes-check: {NOTES} not found", file=sys.stderr)
        return 1

    files = notes_files()
    problems: list[str] = []
    check_empty(files, problems)
    check_index_coverage(files, problems)
    check_links(files, problems)
    check_frontmatter(files, problems)
    check_retrieval_budgets(problems)
    check_skill_canonicalization(problems)

    if problems:
        print(f"notes-check: {len(problems)} problem(s) in dev-notes/\n", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nSee the `dev-notes` skill for the conventions these enforce.",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print(f"notes-check: {len(files)} notes, no problems.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
