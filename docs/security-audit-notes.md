# Security Audit Notes (Frontend)

Running log of `npm audit` findings in `services/frontend/` that are
acknowledged but deferred. Keep entries short and dated. Close them
by linking to the commit that resolves them.

## 2026-04-24 — 9 pre-existing vulnerabilities noted after Radix install

**Trigger:** `npm install --save @radix-ui/react-dialog lucide-react`
reported `9 vulnerabilities (7 moderate, 2 high)` in the post-install
summary (see commit `6d918ba`).

**Verified origin:** None of the advisories originate from the newly
added packages. `npm audit --json` shows the affected paths are:

| Package | Role | Notes |
|---|---|---|
| `react-router`, `react-router-dom` | runtime | SSR/XSS/redirect advisories (GHSA-h5cw-625j-3rxh, GHSA-2w69-qvjg-hvjx, GHSA-8v8x-cx79-35w7, GHSA-9jcx-v3wj-wh4m, GHSA-3cgp-3xvw-98x8). We ship a Vite SPA with no SSR, so most attack surfaces are not reachable in this app. Still worth upgrading. |
| `esbuild`, `vite`, `vitest`, `vite-node`, `@vitest/mocker`, `postcss`, `lodash` | dev-only | Not in production bundle. Low real-world impact; still recommended to upgrade when the test toolchain gets its next bump. |

**Decision:** Defer triage until after Phase 2 (Radix Dialog refactor +
ConfirmDialog + lucide icons). Rationale:

- Nothing is newly introduced. Baseline is unchanged by 6d918ba.
- `react-router-dom` upgrade is a runtime change that should not be
  bundled with a UI refactor.
- Dev-tooling upgrades can be lifted together with the next vitest
  bump (there will likely be one).

**Action items (post-Phase 2):**

1. `npm audit fix` first — see what resolves without breaking changes.
2. If `react-router-dom` still shows after that, evaluate upgrade path.
   We are on `^7.6.3`; the fix range reported is `> 7.11.0`. Check
   migration notes for any breaking changes in our routes.
3. Re-run `npm audit` and either clear this entry or re-scope it with
   remaining items.

**Do not:** run `npm audit fix --force` blindly. It can bump major
versions of dev-tooling without us noticing.
