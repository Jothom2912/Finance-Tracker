# Categorization Baseline

Observability for the categorization pipeline — a cheap, repeatable
way to answer *"is the rule engine actually doing its job?"* before
investing in ML/LLM tiers.

## Why this document exists

The monolith currently wires only the rule-engine tier of the
`CategorizationService` pipeline.  Every transaction lands with a
`categorization_tier` label (one of `rule`, `ml`, `llm`, `fallback`),
already persisted in `transaction-service`'s `transactions` table via
the projection pipeline.

That label is free telemetry.  Before we consider investing in an ML
tier, broader keyword catalogs, or description normalization, we run
three SQL queries against the existing data and let the numbers
point at the right next step.  This keeps us from building a model
for a problem that turns out to be "three kiosks and a restaurant
we could have hardcoded in fifteen minutes".

---

## Running the baseline

Prerequisite: `postgres-transactions` is up (port `5434` on host,
credentials in `docker-compose.yml`).

```bash
psql "postgresql://transaction_service:transaction_service_pass@localhost:5434/transactions"
```

Or from a running container:

```bash
docker exec -it postgres-transactions \
  psql -U transaction_service -d transactions
```

The three queries below are read-only and safe to run against
production data as well as local dev.

### Q1 — per-tier distribution

```sql
SELECT
    COALESCE(categorization_tier, 'null') AS tier,
    COUNT(*)                              AS n,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM transactions
GROUP BY categorization_tier
ORDER BY n DESC;
```

Answers: *how much of the traffic actually falls back?*  The
single headline number the decision gate below depends on.

### Q2 — per-category fallback rate

```sql
SELECT
    category_name,
    COUNT(*) FILTER (WHERE categorization_tier = 'fallback') AS fallback,
    COUNT(*)                                                 AS total,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE categorization_tier = 'fallback')
            / NULLIF(COUNT(*), 0),
        1
    ) AS fallback_pct
FROM transactions
GROUP BY category_name
ORDER BY fallback DESC;
```

Answers: *is the problem concentrated or spread?*  If 80 % of
fallbacks land in 3 categories, keyword expansion is the right fix.
If they're spread across 15+ categories, that points at either a
description-noise problem (normalization) or a structural
rule-engine limit (ML tier).

### Q3 — raw descriptions for every fallback

```sql
SELECT
    description,
    COUNT(*)            AS n,
    SUM(ABS(amount))    AS total_abs
FROM transactions
WHERE categorization_tier = 'fallback'
GROUP BY description
ORDER BY n DESC
LIMIT 100;
```

Answers: *what do the uncategorised transactions actually look
like?*  The top of this list is the shortest-path fix — either
they're the same merchant under three spellings (normalization
problem) or they're merchants the catalog genuinely does not know
about (keyword-catalog problem).

---

## Decision thresholds

**Calibration note**: every threshold below is a hypothesis until
the first baseline run.  They are deliberately written down so
interpretation is not subjective, but they are not dogma.  If the
first run shows 8 % fallback and that feels acceptable for our use
case, edit threshold 1 before the next measurement cycle — record
the change here so the shifted threshold is traceable, not a
silent goal-move.

### Threshold 1 — is fallback rate actually a problem?

| Q1 fallback %       | Interpretation               | Next action                          |
|---------------------|------------------------------|--------------------------------------|
| `< 10 %`            | Acceptable for v1            | No action.  Re-measure next quarter. |
| `10 – 25 %`         | Rule-engine gap              | Proceed to threshold 2 / 3.          |
| `> 25 %`            | Rule-engine structurally insufficient | Plan ML tier on the roadmap. |

### Threshold 2 — is the fallback concentrated?

Only evaluated when threshold 1 lands in the middle band.

| Q2 shape                                           | Interpretation                | Next action                               |
|----------------------------------------------------|-------------------------------|-------------------------------------------|
| Top-3 categories hold `>= 80 %` of fallback volume | Concentrated                  | Keyword expansion for those 3 categories. |
| Top-10 categories hold `< 50 %` of fallback volume | Broadly distributed           | Threshold 3 decides next step.            |
| Anything in between                                | Mixed — treat as concentrated | Keyword expansion for the heaviest 3.     |

### Threshold 3 — description noise?

Only evaluated when threshold 2 lands "broadly distributed".

Manually scan the top-30 rows of Q3.  If the same real-world
merchant appears under 3+ surface forms (e.g. `DK-NOK SEOUL BBQ`,
`VISA/DANKORT SEOUL BBQ COPENHAGEN`, `SEOUL BBQ KBH`), the bottle
neck is description normalization, not keyword coverage.  Add a
normalization step in the rule-engine adapter before considering
an ML tier.

### Decision gate

```mermaid
flowchart TD
    Q1[Q1: fallback %] --> Gate1{< 10%?}
    Gate1 -->|yes| Stop[No action; re-measure next quarter]
    Gate1 -->|no| Gate1b{> 25%?}
    Gate1b -->|yes| ML[Plan ML tier]
    Gate1b -->|no| Q2[Q2: concentration]
    Q2 --> Gate2{Top-3 >= 80%?}
    Gate2 -->|yes| Kw[Keyword expansion for top-3]
    Gate2 -->|no| Gate2b{Top-10 < 50%?}
    Gate2b -->|no| Kw
    Gate2b -->|yes| Q3[Q3: description noise?]
    Q3 --> Gate3{Same merchant under 3+ forms?}
    Gate3 -->|yes| Norm[Add description normalization]
    Gate3 -->|no| ML
```

---

## Baseline results

The table below is filled after each baseline run so history is
visible.  Each row is a commit — bumping the baseline is a
deliberate, reviewable action, not an ambient side-effect.

| Date       | N   | Source                                               | Fallback % (Q1) | Q2 landing category   | Top-3 descriptions (Q3)                                                     | Threshold verdict                           | Action taken |
|------------|-----|------------------------------------------------------|-----------------|-----------------------|-----------------------------------------------------------------------------|---------------------------------------------|--------------|
| 2026-04-22 | 205 | Single Enable Banking sync 2026-04-17, live prod DB. Date range 2026-01-19 → 2026-04-16 (~3 months of own account activity). | 23.4 %          | `Diverse` (48/48 fallbacks, 100 %) — see "Q2 design caveat" below. | `OFF SITE MULTI OSTERBROGA` (6), `KEA V/ SIMPLY COOKING A/S` (5), `KEBABBRO` (4).  Top-10 descriptions cover ~65 % of fallback volume. | Threshold 1 → middle band (10–25 %): rule-engine gap.  Threshold 2 → concentrated *by description cluster*: restaurants / kiosks / cash-processed payments dominate, plus two high-value salary/benefit strings (`LØNOVERFØRSEL` 3×14 091 DKK, `Boligstøtte` 3×2 460 DKK) that should never have fallen back. | Danish-character normalisation fix + Indkomst keyword corrections (next commit). |

### Next planned re-run

**2026-05-20**.  Anchored to roughly one monthly banking cycle after
the 2026-04-22 baseline so the next row covers a second, non-
overlapping sync cohort.  If the date passes without a new row, it
is on whoever owns categorisation that week — not on the queries.
This cadence holds until the baseline table has three data points;
thereafter revisit based on observed drift.

### How to record a run

1. Run Q1/Q2/Q3 against the live database.
2. Append a row to the table above with the top-line numbers.
3. Note which threshold band the result landed in.
4. If an action is taken (keyword expansion, normalisation, ML
   planning), link the commit or issue in the "Action taken" column.
5. Commit the updated `docs/categorization-baseline.md` as part of
   the same change — the baseline and the action must be traceable
   to each other, not drift apart.

### Q2 design caveat (surfaced by 2026-04-22 baseline)

The decision framework assumes Q2's "concentration" signal tells us
whether fallbacks cluster in a few real categories.  In practice the
fallback tier emits a *constant* prediction (currently the category
named `Diverse`), so 100 % of fallbacks trivially land in one row and
threshold 2's "top-3 ≥ 80 %" check is always satisfied regardless of
the underlying distribution.

Q3 is the load-bearing query when the fallback tier is a constant
predictor — descriptions are where the real clustering lives.  Left
here as a note rather than a query rewrite because the constant-
predictor contract may change when the ML tier is wired (a
probabilistic tier would land in multiple categories and restore
Q2's intended signal).  Re-evaluate when that happens.

### Sample-size caveat (2026-04-22 baseline)

N=205 sits right at the "minimum useful" boundary (~200) and comes
from a single sync batch rather than several weeks of organic use.
Trend-questions ("is fallback getting worse over time?") cannot be
answered from one row.  Action decisions driven off this baseline
should prefer interventions with obvious a-priori value
(`LØNOVERFØRSEL` → Indkomst is a bug, not a statistical claim) over
statistically-driven keyword expansions that might be correcting
noise.

### Dual-write status (verified 2026-04-22)

Baseline numbers are quoted against `transaction-service`'s
PostgreSQL (source of truth for categorisation) rather than the
monolith's MySQL.  This is correct for the measurement, but the two
databases are not row-for-row identical and the gap is worth
understanding before the next baseline row is read.

* **`categorization_tier` has a single writer.**  The monolith's
  banking service runs the rule engine in-memory at sync time and
  sends the result via HTTP to `transaction-service`, which
  persists to PostgreSQL and then emits an outbox event that the
  `transaction_sync_consumer` projects to MySQL.  Each row's
  tier is consistent between the two DBs; there is no race.

* **Row counts diverge anyway.**  On 2026-04-22 PostgreSQL held
  205 rows (the 2026-04-17 Enable Banking sync) while MySQL held
  431 — 226 extra rows from two earlier syncs (2026-03-26 and
  2026-04-03) that predate `transaction-service` and were never
  replayed.  MySQL also has 172 duplicate `(description, date,
  amount)` triplets because those earlier syncs overlap in date
  range and the monolith's bank sync had no dedup at the time.
  Tracked as a separate followup in `docs/followups.md`; not a
  categorisation-accuracy concern, but it skews any analytics
  run directly against MySQL.

* **What this means for the baseline.**  The 23.4 % fallback
  reading is a valid measurement of *what the current rule engine
  produces on new bank data flowing through the new pipeline*.
  It is **not** the historical fallback rate across all
  transactions the user has ever recorded — MySQL's older cohorts
  show 26.1 % (2026-03-26) and 31.3 % (2026-04-03) fallback, but
  those numbers reflect an earlier state of the rule engine and
  are not directly comparable.  Use PostgreSQL as the baseline
  reference; treat MySQL's historical cohorts as context, not as
  drift evidence.
