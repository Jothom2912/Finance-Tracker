---
title: <Finding title>
date: YYYY-MM-DD
severity: MEDIUM        # CRITICAL | HIGH | MEDIUM | LOW
area: <service or cross-cutting>
status: open            # open | in-progress | resolved | wont-fix
backlog: []             # e.g. [P1-15] — the item(s) that schedule this. Fill it in as soon
                        # as the item exists: without it, `grep -rn P1-15 dev-notes/` misses
                        # the finding that motivated the work.
resolved-by: null       # link to plan/commit when resolved
---

# <Finding title>

**Where**: `path/to/file.py:123`

**Defect**: One sentence — what is wrong.

**Why it matters**: Failure scenario or cost (perf, scaling, maintenance).

**Suggested fix**: Functionality-preserving refactor direction.
