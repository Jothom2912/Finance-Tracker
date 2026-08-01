---
title: Codex-ready dev-notes and bounded retrieval
date: 2026-08-01
status: done
backlog: [P3-65]
related: [../README.md, ../STATUS.md, ../backlog/BACKLOG.md]
---

# Codex-ready dev-notes and bounded retrieval

## Goal

Make the repository instructions and dev-notes workflows discoverable by Codex, while
reducing the mandatory context needed to begin useful work. Completion means Codex can find
the repository skills from a fresh session, the first-pass notes path is bounded and concise,
and deterministic checks prevent `STATUS.md`, the main index and backlog rows from growing
back into narrative archives.

## Context

The knowledge base is internally consistent (`make notes-check`: 148 notes, no problems), but
its progressive-disclosure contract has drifted:

- `STATUS.md` says it is roughly 20 lines but is 634 lines / 6,420 words / 47 KB.
- `00-INDEX.md` is 132 lines but 3,641 words because many hooks contain outcome narratives.
- `backlog/BACKLOG.md` is 756 lines / 17,161 words / 130 KB; its tables are intended as the
  cheap queue, but live in the same file as all item details.
- Repository skills live only in `.claude/skills`; Codex discovers repository skills from
  `.agents/skills`.
- The root conventions live in ignored lowercase `claude.md`; Codex expects tracked
  `AGENTS.md`, so neither Codex nor a fresh clone receives those conventions.
- Plan frontmatter uses both `backlog-items:` and `backlog:` even though retrieval treats the
  backlog ID as the primary key.

No existing backlog item or plan covers Codex discovery or dev-notes context cost, so this is
filed as P3-65.

## Non-goals

- Do not rewrite historical findings, decisions, plan outcomes or session logs for style.
- Do not change application behavior, service architecture, tests or deployment.
- Do not delete historical findings or decisions.
- Do not create a plugin or MCP server; repository-local skills are sufficient.
- Do not split every existing backlog detail into a new file in this pass. First make
  retrieval bounded; migrate details only if measurement shows that it is still necessary.
- Preserve Claude compatibility without maintaining two independent copies of instructions
  or skills.

## Steps

1. [x] **Capture baselines and invariants.** Record line/word/byte counts for `STATUS.md`,
   `00-INDEX.md`, `backlog/BACKLOG.md` and the three skills. Define budgets from actual use:
   `STATUS.md` <= 100 lines and 1,200 words; index hooks one physical line and <= 240
   characters; backlog table rows one physical line. Document that these are retrieval
   budgets, not prose-style rules.

2. [x] **Make Codex discovery canonical.** Add a tracked root `AGENTS.md` containing durable
   repository workflow, verification and architecture conventions, corrected against current
   notes/code. Move the canonical skill folders to `.agents/skills/{dev-notes,
   dev-notes-plan,dev-notes-decision}`. Preserve Claude support through tracked compatibility
   links or thin forwarding files so there is one source of truth. Remove the obsolete
   `claude.md` ignore rule and eliminate the ignored lowercase file once its useful content is
   represented canonically.

3. [x] **Tighten the three skills.** Make descriptions goal- and trigger-oriented; use `rg`
   examples; cap initial retrieval at the smallest relevant set; forbid whole-file backlog
   reads when an ID/heading is known; make plan creation conditional on genuine multi-step or
   design work; distinguish permanent plan outcomes from resumable session state. Add
   `agents/openai.yaml` UI metadata generated with Codex's skill-creator tooling.

4. [x] **Add deterministic bounded retrieval.** Add a stdlib-only helper under the
   `dev-notes` skill, accepting `--id`, `--area` or `--path`. It prints paths and bounded
   matching excerpts for status, backlog, findings, plans and decisions without dumping the
   vault. Test at least one backlog ID, one service area, no matches and invalid arguments.

5. [x] **Reduce `STATUS.md` to current state.** Keep only active work, a short recently
   shipped list, next candidates, blockers and at most eight standing traps with links.
   Remove the embedded historical release narratives; their canonical copies remain in plan
   outcomes and session logs, with Git retaining the prior living-document revision.

6. [x] **Restore `00-INDEX.md` as a routing index.** Reduce each hook to one clause answering
   “when should this file be opened?”. Remove commit lists, measurements and outcome reports
   from index entries. Keep session indexing separate. Do not remove indexed documents.

7. [x] **Standardize metadata and writing boundaries.** Change the plan template and existing
   plan frontmatter from `backlog-items:` to `backlog:` where necessary. Update
   `dev-notes/README.md` to point at `.agents/skills`, define the STATUS/index budgets and
   clarify: plan `Outcome` owns the shipping narrative; session logs only preserve resumable
   state, cross-item discoveries or open ends.

8. [x] **Strengthen `notes-check`.** Extend `scripts/notes_check.py` and its tests/fixtures (or
   add focused tests if none exist) to reject oversized `STATUS.md`, multiline/overlong index
   hooks, multiline backlog table rows where detectable, unsupported plan metadata and stale
   `.claude/skills` duplicates. Error messages must name the file, violated budget and repair
   direction.

9. [x] **Validate discovery and retrieval.** Run the skill creator's `quick_validate.py` on
   every `.agents/skills/*` folder; run representative context-helper queries; run
   `make notes-check`; use `git diff --check`; and start a fresh non-mutating Codex command if
   the local CLI is available to confirm that `AGENTS.md` and all three skills are discovered.
   Measure the final entry-document sizes against the baseline.

10. [x] **Close out P3-65.** Fill this plan's Outcome with before/after measurements and any
    deliberately deferred backlog split; mark P3-65 done; update `STATUS.md`; write a session
    log only if it contains information not already captured here; run `make notes-check`
    again.

## Verification

```bash
wc -l -w -c dev-notes/STATUS.md dev-notes/00-INDEX.md dev-notes/backlog/BACKLOG.md
python3 .agents/skills/dev-notes/scripts/context.py --id P3-65
python3 .agents/skills/dev-notes/scripts/context.py --area account-service
python3 /path/to/skill-creator/scripts/quick_validate.py .agents/skills/dev-notes
python3 /path/to/skill-creator/scripts/quick_validate.py .agents/skills/dev-notes-plan
python3 /path/to/skill-creator/scripts/quick_validate.py .agents/skills/dev-notes-decision
make notes-check
git diff --check
```

The implementation must substitute the actual installed skill-creator path in the validation
commands and record it in Outcome. If `codex` is installed, also run a fresh read-only command
that lists active instruction and skill sources; absence of the CLI is a reported limitation,
not a reason to skip structural validation.

## Risks & rollback

- **Useful context is cut with the narrative.** Before deleting a STATUS/index paragraph,
  verify that its durable claim exists in a linked plan outcome, decision, finding, pattern or
  session. Move a genuinely unique claim to its proper owner rather than retaining history in
  an entry document.
- **Claude compatibility breaks.** Keep compatibility links/forwarders until both directory
  layouts have been inspected. Never maintain duplicated skill bodies.
- **Checks encode arbitrary aesthetics.** Enforce only the measured retrieval contracts
  (bounded entry docs, one-line hooks/rows, canonical metadata), with explicit limits and
  actionable errors.
- **Mechanical frontmatter migration breaks retrieval.** Search both keys before and after,
  and require every prior backlog ID hit to remain discoverable.
- **Large cleanup diff hides unrelated edits.** Keep phases separable and do not touch
  application code. Roll back an individual phase by reverting its focused commit/diff rather
  than reverting the whole cleanup.

## Outcome

Completed 2026-08-01.

- Added tracked `AGENTS.md` and made `.agents/skills` canonical. `CLAUDE.md` and the three
  `.claude/skills` entries are compatibility symlinks, so both agents read one source.
- A fresh read-only Codex 0.146.0 session reported `AGENTS.md` plus repository skills
  `dev-notes`, `dev-notes-decision` and `dev-notes-plan`; discovery is measured, not inferred.
- Rewrote the skills around bounded retrieval and generated `agents/openai.yaml` metadata.
  The metadata generator itself could not run under system Python because PyYAML was absent;
  the same schema was written directly, then all three skills passed the official validator
  through `uv run --with pyyaml` using
  `/Users/johannesprivat/.codex/skills/.system/skill-creator/scripts/quick_validate.py`.
- Added `context.py` with mutually exclusive `--id`, `--area` and `--path` inputs, ranking exact
  owners above incidental prose. Verified P3-65, account-service, invalid-ID and no-match paths.
- Reduced `STATUS.md` from **634 lines / 6,420 words / 47,429 bytes** to
  **61 lines / 421 words / 3,335 bytes**. Historical narratives remain owned by linked plan
  outcomes, decisions, findings and Git history.
- Reduced `00-INDEX.md` from **132 lines / 3,641 words / 35,817 bytes** to
  **133 lines / 2,017 words / 24,215 bytes**, preserving every indexed document while capping
  each routing hook at 240 characters.
- Standardized all plan frontmatter and the template from `backlog-items:` to `backlog:`.
- Extended `notes_check.py` with STATUS line/word budgets, one-line/240-character index hooks,
  physical backlog-row checks, canonical plan metadata and stale-skill detection. Added focused
  stdlib regression tests; both tests pass.
- Deliberately deferred splitting `BACKLOG.md`: it remains 757 lines / 17,194 words, but ID and
  area retrieval no longer requires reading it whole. Revisit a physical split only if usage
  shows the bounded helper is insufficient.

Final verification: three official skill validations passed; fresh Codex discovery passed;
`python3 -m unittest scripts/test_notes_check.py`, `make notes-check` (149 notes) and
`git diff --check` all passed. No application code or runtime behavior changed.
