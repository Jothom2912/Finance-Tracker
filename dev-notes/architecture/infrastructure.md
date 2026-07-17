---
title: Infrastructure, deployment & cross-cutting duplication
updated: 2026-07-07
source: architecture audit 2026-07-07
---

# Infrastructure & cross-cutting

## Deployment topology

- **Compose** (802 lines, primary dev runtime): redis, 8× postgres (one per service), rabbitmq, ollama (+ one-shot `ollama-pull`), 10 API services, 16 worker/consumer containers (incl. `budget-month-close-scheduler`, F1-07 — first user of the [worker-loop scheduler pattern](../decisions/2026-07-17-scheduler-pattern-worker-loop.md)). Frontend NOT in compose (`make dev-frontend`).
- **Kubernetes** (`k8s/`, flat Kustomize, no base/overlays): superset of compose — all apps + 19 workers + infra + frontend + KEDA health ScaledJob + HPA (user & transaction only) + in-cluster monitoring. Images `finance-tracker/*:local`, `imagePullPolicy: Never` → local clusters only. `replicas: 1` everywhere.
- **Monitoring**: dual stacks (compose overlay + `k8s/monitoring/`), black-box only (no app exposes `/metrics`; deliberate per `docs/MONITORING.md`). Only 2 alert rules. Config duplicated between `monitoring/` and `k8s/monitoring/config/`.
- **CI**: GitHub Actions matrix (ruff + bandit + pytest) for **7 of 10** Python services — categorization, banking, saga missing; bandit neutered with `|| true`; e2e job can pass green with all tests skipped (conftest skips when health endpoints unreachable; the gitignored PEM bind-mount breaks banking-service in CI invisibly).
- **Tests**: ~650 (490 Python + 170 Vitest); root `make test` covers only 6 of 11 services; e2e covers health/auth/tx CRUD/CSV/budget-close but NOT bank sync saga, categorization outcomes, or ai-service; pyright scoped to goal-service + contracts only.

## Cross-service duplication map (measured, md5/diff)

| Pattern | Copies | Status |
|---|---|---|
| `app/workers/outbox_publisher.py` | 8 services | 7 near-identical (3–12 lines differ); account-service a 175-line divergent rewrite |
| `rabbitmq_publisher.py` | 7 | user ≡ transaction byte-identical; rest 2–11 lines differ |
| `app/auth.py` (JWT) | 9 + dead `shared/auth/jwt_utils.py` (0 importers) | same pattern; account (241 ln) & gateway (101 ln) diverged; budget mints service tokens |
| `app/config.py` | 12 | same pattern, differing secret defaults (some fail-open with `""`) |
| Dockerfile | 14 | 7 near-identical uv-template |
| alembic `env.py` | 7+1 | near-identical |
| logging setup | ~20 worker files | inline `logging.basicConfig` everywhere, no shared module |
| `budget_period.py` | 3 (gateway, budget, account) | byte-identical triplicate (from gateway audit) |

`services/shared/contracts` (43 importers, uv path dependency) proves the sharing mechanism works — everything above belongs next to it.

## Known issues already on record (docs/)

- `docs/followups.md`: ADR-0003 goal-allocation flow unfinished; frontend 757 kB single bundle; deleted transaction HTTP-layer integration tests (lost 401/IDOR coverage); Ryuk disabled on Windows; taxonomy follow-ups (PlannedTransaction lacks subcategory, "Anden" fallback pinned by name, legacy budget payload keys, dead `is_user_confirmed`).
- ADRs: **two colliding numbering schemes** (`docs/adr/000N-*` vs `docs/ADR-00N-*`). ADR-003 consolidated taxonomy in categorization-service.
- `docs/security-audit-notes.md`: frontend npm-audit only (9 vulns, DEFERRED). No backend security notes exist.

## Headline infra findings

Full list in [findings/2026-07-07-architecture-audit.md](../../findings/2026-07-07-architecture-audit.md): production EB private key in repo working tree (CRITICAL), real personal transaction data committed in `scripts/backups/*.jsonl` (CRITICAL), plaintext secrets in `k8s/secrets.yaml` incl. real EB app id (HIGH), empty-string JWT fallbacks in ai/gateway config (HIGH), e2e-can-skip-everything CI (HIGH), compose ai-service points at host Ollama while compose pulls 5 GB into an unused container (MEDIUM), no healthchecks/restart policies on API containers, `account-outbox-publisher` has no restart policy at all (MEDIUM), 2 of ~50 k8s Deployments have resource requests (MEDIUM).
