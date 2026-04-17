# ADR-0001: Frontend uses npm, not yarn

**Date:** 2026-04-17
**Status:** Accepted
**Context:** Divergence from workspace rule `package-managers.mdc`, which mandates yarn for all React projects.

## Decision

The frontend (`services/frontend/`) uses **npm**. `package-lock.json` is the committed lockfile. There is no `yarn.lock` and none is planned.

## Rationale

The workspace rule is a template default. For this repository:

- **`package-lock.json` is the source of truth.** It has been the only committed lockfile since the frontend was moved into the monorepo. `node_modules` has always been installed from it.
- **No yarn-specific features are used.** No workspaces, no Plug'n'Play, no selective dependency resolution. npm covers every need the project actually has.
- **The cost of migration is real and the benefit is abstract.** Moving to yarn requires `corepack enable` (which needs admin on Windows), generating a new lockfile, deleting the old one, updating CI, and teaching every future contributor why the rule doesn't apply here — all to gain no concrete capability.
- **One developer, one machine.** The multi-developer consistency argument that normally justifies a shared package manager doesn't apply.

## Lesson behind the decision

This ADR exists because a mismatch between documentation (which said `yarn dev`) and reality (which had an npm `package-lock.json`) caused `make dev-frontend` to fail on a clean machine. The fix was not to install yarn — it was to recognise that **the lockfile is the source of truth**, and every other reference (Makefile, README, workspace rules) must align with it, not the other way around.

## Consequences

- `services/frontend/Makefile` calls `npm install` / `npm run dev`, not yarn.
- All documentation uses `npm` in code blocks.
- A project-scope Cursor rule (`.cursor/rules/package-managers-override.mdc`) overrides the global template rule so AI agents do not re-introduce yarn.
- If a future decision adds yarn-specific capability (e.g. workspaces for a mobile app sharing code with the frontend), this ADR should be superseded rather than silently edited around.

## ADR convention

This file establishes the ADR numbering convention for the repository:

- Location: `docs/adr/`
- Filename: `NNNN-short-title-kebab-case.md` (4-digit zero-padded sequence)
- Each ADR is immutable after acceptance; supersede with a new ADR rather than editing in place.
