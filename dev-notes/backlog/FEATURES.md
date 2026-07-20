# Feature backlog — future features & product improvements

Companion to [BACKLOG.md](BACKLOG.md) (technical debt). IDs `F1/F2/F3-xx` are stable — never renumber.
Prioritization principle: **finish what's half-built → high-value user features → bigger bets.**
Each item lists *Builds on* (existing scaffolding — this is why it's cheap) and *Needs first* (technical backlog prerequisites).
Implementation sequencing + build sketches: [plans/2026-07-07-feature-roadmap.md](../plans/2026-07-07-feature-roadmap.md).

## F1 — Now: finish the half-built (highest leverage, scaffolding already exists)

| ID | Feature | Value | Builds on | Needs first | Effort | Status |
|----|---------|-------|-----------|-------------|--------|--------|
| F1-01 | **Notification service MVP** — goal-reached + month-closed + bank-sync-done notifications, in-app feed (email deferred) | Users find out things happened without opening the dashboard | Stub service exists (port 8008 reserved); all trigger events already flow on RabbitMQ (`budget.month_closed`, `goal.updated`, `bank.sync.completed`) | P2-01 (shared consumer base) ✓ | M | **in-progress** (plan 2026-07-20: v1 = 3 triggers, email deferred to `IEmailPort`+log adapter — [plan](../plans/2026-07-20-f101-notification-service-mvp.md)) |
| F1-02 | **User-defined categorization rules** — UI to add "description contains X → category Y", per-user priority over seed rules | Auto-categorization stops being wrong in the same way twice | `categorization_rules` table + full `PostgresRuleRepository` already exist (currently dead — audit H19); rule engine supports priorities | P2-06 (wire rules DB into engine) | M | **done 2026-07-17** (`/api/v1/rules` + TieredRuleEngine + `/rules` UI; e2e-verified — [plan](../plans/2026-07-17-user-rules-and-feedback-loop.md)) |
| F1-03 | **Categorization feedback loop** — manual category correction on a transaction teaches the system | Accuracy improves with use instead of staying static | ~~merchant upsert w. `is_user_confirmed`~~ superseded: corrections stored as auto-managed user *rules* (priority 10) — see [decision](../decisions/2026-07-17-learned-corrections-as-rules.md); `tier="manual"` guard protects corrections | P2-06 | M | **done 2026-07-17** (`transaction.category_corrected` event + learning consumer; e2e-verified) |
| F1-04 | **Complete goal allocation flow (ADR-0003)** — surplus → goal end-to-end incl. frontend visibility of allocations | The flagship "your surplus becomes savings" story actually demoable | Backend allocation handler is the best-engineered consumer in the repo; docs/followups lists the exact missing pieces (consumer/publisher/frontend) | P1 done (✓) | M | **done 2026-07-17** (default-goal API + history/unallocated read APIs + goals-UI + "Luk måned"-knap; e2e-verified — [plan](../plans/2026-07-17-f104-goal-allocation-completion.md), [decision](../decisions/2026-07-17-manual-month-close-button.md)) |
| F1-07 | **Scheduled month-close (day-7)** — ADR-0003's original v1 trigger: auto-close previous budget month per account on day 7 | Months close without user discipline; kills the "closed too early on incomplete numbers" risk | Close endpoint + button exist (F1-04); pairs with F1-05's scheduler infra decision (worker loop vs KEDA cron) | F1-05 scheduler pattern (or build first here) | S | **done 2026-07-17** (worker-loop scheduler container; e2e-verified — [plan](../plans/2026-07-17-f107-scheduled-month-close.md), [scheduler-decision](../decisions/2026-07-17-scheduler-pattern-worker-loop.md)) |
| F1-05 | **Scheduled/automatic bank sync** — nightly sync per active connection instead of manual button; reconsent prompt when consent nears expiry | The app stays current without user effort — the single biggest UX gap | Whole saga pipeline exists and is now honest about failures (P1-12 ✓); scheduler pattern settled + reference implementation exists (F1-07's month-close worker — [decision](../decisions/2026-07-17-scheduler-pattern-worker-loop.md)) | P2-08 ✓; P3-14 ✓ (2026-07-17 — scheduler kan ikke race knappen) | M | **done 2026-07-17** (staleness-baseret worker; reconsent-fladen er v1-logs — UI-banner venter på F1-01; e2e-verified — [plan](../plans/2026-07-17-f105-scheduled-bank-sync.md)) |
| F1-06 | **Wire ML categorization tier** — embeddings/classifier for transactions the rule engine misses | Fewer "Anden" fallbacks without waiting for user rules | Tier orchestrator has ML/LLM slots ready (`Optional` ports); Ollama + bge-m3 already running for ai-service | P2-06; F1-03 gives training signal | L | open |

## F2 — Next: high-value user features

| ID | Feature | Value | Builds on | Needs first | Effort | Status |
|----|---------|-------|-----------|-------------|--------|--------|
| F2-01 | **Recurring transactions & subscriptions overview** — detect recurring merchants/amounts, list subscriptions with monthly cost | "You pay 438 kr/md across 6 subscriptions" — top user-requested feature class in PFM | Dedup key + denormalized merchant descriptions; `planned_transactions` model for confirmed recurrences | P1-07 (✓ efficient queries) | M | open |
| F2-02 | **Cash-flow forecast** — project month-end balance from planned + recurring + budget pace | Answers "can I afford this?" — turns tracker into advisor | `planned_transactions` (exists), F2-01 detections, budget lines | F2-01 | M | open |
| F2-03 | **Mid-month budget alerts** — "80% of Dagligvarer used, 12 days left" | Budgets become preventive instead of forensic | Notification service (F1-01), budget summary logic in budget-service | F1-01 | S | open |
| F2-04 | **Semantic transaction search in UI** — search box backed by the existing ChromaDB retrieval | "netflix sidste år" just works; showcases the RAG infra outside chat | ChromaDB search + tenant isolation already built and tested for chat | ~~P3-04~~ unblocked 2026-07-14: AI-20 hybrid-endpoint er event-synced — byg mod `POST /api/v1/analytics/search/hybrid` | S | open |
| F2-05 | **Monthly report export** — PDF/CSV month summary (income/expenses/categories/goals) via gateway aggregation | Shareable/archivable statements; accountant-friendly | Gateway already aggregates exactly this data for the dashboard | P2-04 (gateway perf) nice-to-have | M | open |
| F2-06 | **AI chat expansion** — new intents: spending trends, forecast ("har jeg råd til…"), budget advice; proactive monthly insight message | Chat becomes useful beyond lookup | Router's constrained-intent design makes adding intents cheap; F2-02 provides forecast data | F2-02 for forecast intent | M | open |
| F2-07 | **Dashboard month-picker semantics cleanup + budget-period awareness everywhere** | Removes the documented confusion between calendar month and budget period | `budget_period.py` (being centralized in P2-03); followups item | P2-03 | S | open |

## F3 — Later: bigger bets

| ID | Feature | Value | Builds on | Needs first | Effort | Status |
|----|---------|-------|-----------|-------------|--------|--------|
| F3-01 | **Household / shared accounts** — invite a partner to shared account groups, shared budgets & goals | Expands from personal to household finance | `account_groups` + membership tables exist (currently auth'ed but unscoped) | Ownership model for groups (P1-05 carry-over) — hard prerequisite | L | open |
| F3-02 | **Net worth tracking** — balance history per account + manual assets/liabilities | The "big picture" number over time | Banking service can fetch balances from EB; account model extensible | F1-05 (scheduled sync gives the time series) | L | open |
| F3-03 | **Multi-currency support** | Foreign accounts/travel spend correct | ~~P2-09~~ unblocked 2026-07-16: currency stored on transactions + on `TransactionCreatedEvent`. Remaining scope: ES mapping bump, gateway GraphQL types, currency-aware aggregations, display | — (prerequisite met) | L | open |
| F3-04 | **PWA / mobile experience** — installable, offline-readable dashboard, push notifications | Daily-use surface; push pairs with F1-01 | Vite SPA; NotificationContext | F1-01 for push | L | open |
| F3-05 | **Frontend TypeScript migration** (improvement) — incremental, new files first | Kills the snake_case/camelCase leak class of bugs at compile time | Vite supports mixed TS/JSX; API normalization from P3-06 | P3-06 first | L | open |
| F3-06 | **i18n (Danish/English toggle)** | Shareability, demo value | Strings are mostly centralized in components | — | M | open |

## Rejected / parked (with reason)

- **Crypto/stock portfolio tracking** — different data domain (market feeds), low synergy with PSD2 core. Revisit only after F3-02.
- **Receipt scanning/OCR** — high effort, marginal value while categorization accuracy (F1-02/03/06) is the real gap.
- **Social/comparison features** — privacy posture of this app (personal financial data) argues against; no.
