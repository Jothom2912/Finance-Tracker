---
title: k8s manifests have drifted 5 features behind docker-compose
date: 2026-07-25
severity: MEDIUM
area: infrastructure
status: open
backlog: [P2-21]
resolved-by: null
---

# k8s manifests have drifted 5 features behind docker-compose

**Where**: `k8s/kustomization.yaml`, `k8s/apps/`, `k8s/workers/`, `k8s/infra/` — compared
against `docker-compose.yml`.

**Defect**: Six workloads and one database exist in compose but have no k8s manifest and no
`kustomization.yaml` entry:

| Missing from k8s | Compose ref | Feature |
|---|---|---|
| `notification-service` | `docker-compose.yml:1035` | F1-01 |
| `notification-consumer` | `docker-compose.yml:1059` | F1-01 |
| `postgres-notifications` | `docker-compose.yml:1018` | F1-01 |
| `banking-sync-scheduler` | `docker-compose.yml:788` | F1-05 |
| `budget-month-close-scheduler` | `docker-compose.yml:635` | F1-07 |
| `budget-alert-scheduler` | `docker-compose.yml:660` | F2-03 |
| `analytics-embedding-consumer` | `docker-compose.yml:878` | AI-20 |

Verified 2026-07-25: `grep -n "notification\|budget-alert" k8s/kustomization.yaml
k8s/configmap.yaml k8s/secrets.yaml` returns nothing.

**Why it matters**: `kubectl apply -k k8s/` silently produces a system that looks complete
and is not. The three schedulers are what make the ADR-0003 chain (sync → month-close →
goal allocation) automatic, so a k8s deployment quietly reverts the product to
manual-button-only — with no error, no crash, no missing-image event. Nothing fails; things
simply never happen. The notification feed additionally has no backing database at all in
k8s, so the bell would 500 rather than degrade.

The drift is not a one-off: it has accumulated across every feature shipped since AI-20
(2026-07-14), which means the compose file is the de-facto deployment spec and `k8s/` is
documentation that has stopped being true. That is the expensive part — a stale manifest
set is worse than an absent one, because it invites trust.

**Suggested fix**: Add the seven manifests mirroring the existing conventions —
`k8s/apps/account-service.yaml` for the API+Service shape, any file in `k8s/workers/` for
the command-override worker shape, `k8s/infra/postgres-account.yaml` for the database — plus
`DATABASE_URL_NOTIFICATION_SYNC` in `secrets.yaml` and the `kustomization.yaml` entries.

Then make the drift detectable rather than relying on review: a CI step that diffs the
service names in `docker-compose.yml` against the resources in `kustomization.yaml` and
fails on an un-allowlisted difference. Without that check this finding will recur on the
next feature — it already has, four times.

Deliberately scoped out of
[plans/2026-07-25-notification-service-hardening.md](../plans/2026-07-25-notification-service-hardening.md)
(decision 2026-07-25): fixing only notification's third of it would leave the other four
features broken and the systemic cause untouched. Tracked as P2-21.
