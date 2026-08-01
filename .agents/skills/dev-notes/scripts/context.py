#!/usr/bin/env python3
"""Print bounded dev-notes matches for an ID, area, or repository path."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
NOTES = REPO_ROOT / "dev-notes"
SEARCH_DIRS = ("backlog", "findings", "plans", "decisions", "architecture", "patterns")
MAX_FILES = 8
MAX_MATCHES_PER_FILE = 4
CONTEXT_LINES = 2


def terms_for(args: argparse.Namespace) -> list[str]:
    if args.id:
        value = args.id.strip().upper()
        if not re.fullmatch(r"(?:P[123]|F[123]|AI|ML)-\d+[A-Z]?", value):
            raise SystemExit(f"invalid work ID: {args.id}")
        return [value]
    value = (args.area or args.path).strip().rstrip("/")
    if not value:
        raise SystemExit("search value must not be empty")
    terms = [value]
    leaf = Path(value).name
    if leaf and leaf != value:
        terms.append(leaf)
    if leaf.endswith("-service"):
        terms.append(leaf.removesuffix("-service"))
    return list(dict.fromkeys(terms))


def matching_lines(path: Path, terms: list[str]) -> list[int]:
    lowered = [term.casefold() for term in terms]
    return [
        number
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if any(term in line.casefold() for term in lowered)
    ]


def relevance(path: Path, matches: list[int], terms: list[str]) -> int:
    """Prefer exact service/path owners over incidental prose mentions."""
    text = path.read_text(encoding="utf-8").casefold()
    primary = terms[0].casefold()
    score = min(len(matches), MAX_MATCHES_PER_FILE)
    score += text.count(primary) * 10
    if primary in path.as_posix().casefold():
        score += 80
    if path.name == "STATUS.md":
        score += 100
    if re.search(rf"^area:\s*.*{re.escape(primary)}", text, re.MULTILINE):
        score += 60
    return score


def render_excerpt(path: Path, matches: list[int]) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    selected: set[int] = set()
    for number in matches[:MAX_MATCHES_PER_FILE]:
        selected.update(range(max(1, number - CONTEXT_LINES), min(len(lines), number + CONTEXT_LINES) + 1))
    body = "\n".join(f"{number:>5}: {lines[number - 1]}" for number in sorted(selected))
    return f"\n## {path.relative_to(REPO_ROOT).as_posix()}\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--id", help="work ID, for example P2-43 or F2-08")
    group.add_argument("--area", help="service or cross-cutting area")
    group.add_argument("--path", help="repository path whose basename should be retrieved")
    args = parser.parse_args()
    terms = terms_for(args)

    candidates = [NOTES / "STATUS.md"]
    for directory in SEARCH_DIRS:
        candidates.extend(sorted((NOTES / directory).rglob("*.md")))

    results: list[tuple[Path, list[int]]] = []
    for path in candidates:
        matches = matching_lines(path, terms)
        if matches:
            results.append((path, matches))
    results.sort(key=lambda item: (-relevance(item[0], item[1], terms), item[0].as_posix()))
    results = results[:MAX_FILES]

    print(f"query: {', '.join(terms)}")
    print(f"matches: {len(results)} file(s); limit: {MAX_FILES} files / {MAX_MATCHES_PER_FILE} hits each")
    if not results:
        return 1
    for path, matches in results:
        print(render_excerpt(path, matches))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
