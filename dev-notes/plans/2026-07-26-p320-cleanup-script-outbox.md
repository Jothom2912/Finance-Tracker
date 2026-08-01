---
title: P3-20 — cleanup-scriptet skriver outbox-row i samme transaktion
date: 2026-07-26
status: done
backlog: [P3-20, P3-21]
related:
  - findings/2026-07-25-cleanup-script-desyncs-read-model.md
  - patterns/transactional-outbox.md
  - decisions/2026-07-25-budget-spend-from-analytics.md
---

# P3-20 — cleanup-scriptet skriver outbox-row i samme transaktion

## Goal

`scripts/cleanup_pg_duplicates.py` skal skrive en `TransactionDeletedEvent`-outbox-row i
samme transaktion som sin `DELETE`, så ES-read-modellen lærer om sletningen ad den samme
sti som servicens eget delete. Derefter afstemmes den ene eksisterende fantom-række.

**Færdig når**: `--execute` på en dublet får `transactions_v2` til at sætte
`is_deleted: true` på den slettede række uden manuel indgriben, og id-sæt-diffen mellem
Postgres og ES for rigtige brugere er tom.

## Context

[P3-20-fundet](../findings/2026-07-25-cleanup-script-desyncs-read-model.md) blev fundet ved
måling under P1-13: analytics rapporterede 17 666,17 for konto 1 / juli hvor Postgres siger
17 528,17. Differencen er tx 1119 (138,00), som scriptet slettede uden event.

Det haster mere efter [P1-13](../decisions/2026-07-25-budget-spend-from-analytics.md):
budget-service læser nu forbrug fra præcis den read-model, så en fantom-række inflaterer
både `close_month`-overskuddet og F2-03's alarm-tærskler.

### Målt tilstand 2026-07-26 (før ændring)

Fuld id-sæt-diff, ikke kun juli (fundet diffede kun én måned):

| | Postgres | ES (`is_deleted:false`) |
|---|---|---|
| Rækker i alt | 284 | 351 |
| Konto 1 / juli / expense | 53 → 17 528,17 | 54 → **17 666,17** |

Diffen er **67 fantomer, 0 manglende** — projektionen er ellers sund, lækagen er ensrettet.
De 67 falder i to grupper med hver sin årsag:

- **tx 1119** — den ene rigtige fantom (user 1). Denne plan.
- **9000001–9000901 (66 stk.)** — eval-fixtures fra `services/ai-service/tests/eval/es_seed.py`,
  som seeder direkte ind i produktions-indexet. De hører til user 9001/9002, så alle queries
  filtrerer dem væk fra rigtige brugere. **Uden for scope** — filer som selvstændigt fund.

### To fund undervejs som ændrer planen

1. **Der ligger 2 rigtige dubletter i DB'en lige nu** (id 864 og 1024, 30,00 og 120,00).
   Køres `--execute` i dag, får vi to nye fantomer. Efter fixet bliver de i stedet den
   ægte e2e-verifikation — men det er en mutation af rigtige data, se Risks.
2. **Scriptet har ingen dokumenteret kørsels-kontekst.** Der er ingen root-`pyproject`, og
   docstringens `uv run python scripts/...` virker ikke. Verificeret virkende invocation:
   `uv run --project services/transaction-service python scripts/cleanup_pg_duplicates.py`
   — den venv har både `psycopg2` og `contracts` som path-dependency. Det er også den
   rigtige venv, eftersom scriptet skriver i transaction-services DB.

### Verificeret kæde (så event'et faktisk virker)

- `transaction.deleted` → kun to bindings: `analytics.transactions` og `analytics.embeddings`
  (begge `transaction.*`). Ingen andre consumers påvirkes.
- `projections.py:94 handle_deleted` → `transaction_store.mark_deleted` → painless-script
  sætter `is_deleted = true`. `scripted_upsert` gør den sikker selv hvis dokumentet mangler.
- Outbox-worker'en bruger `routing_key = entry.event_type`, så rækken kræver ingen ekstra
  routing-metadata.

## Non-goals

- **Scriptets slette-semantik ændres ikke.** Samme dedup-nøgle, samme "behold laveste id",
  samme dry-run-default, samme FK-tjek, samme JSONL-audit. Kun event-emissionen er ny.
- **Ingen ny infrastruktur.** Vi kalder ikke transaction-services delete-API (option 2 i
  fundet); den kræver auth og gør et vedligeholdelses-script til en service-klient.
- **De 66 eval-fixtures i ES røres ikke.**
- **P2-25 (soft-delete på transactions) besluttes ikke her.** Denne plan gør hard-delete
  event-korrekt; den afgør ikke om hard-delete er det rigtige.
- **Ingen retro-korrektion af lukkede måneder.** Samme afgrænsning som P1-13.

## Steps

1. [ ] **Kørsels-kontekst i docstring** — `scripts/cleanup_pg_duplicates.py`.
   Ret Usage til `uv run --project services/transaction-service ...` og skriv *hvorfor*
   (venv'en ejer både DB-forbindelsen og `contracts`). ~6 linjer docstring.

2. [ ] **Byg outbox-rækken fra det rigtige kontrakt-objekt** — samme fil.
   Ny ren funktion `_build_outbox_row(row: dict) -> tuple` som importerer
   `TransactionDeletedEvent` fra `contracts` og returnerer
   `(uuid4, "transaction", str(id), event.event_type, event.to_json(), event.correlation_id, "pending", 0)`.
   `_find_duplicates` returnerer allerede `user_id`, `account_id`, `amount` — alt hvad
   kontrakten kræver. Importen af det rigtige event er hele pointen: så kan payloaden
   ikke drifte fra kontrakten.

3. [ ] **Insert i samme transaktion som DELETE** — `_delete_rows`.
   `execute_values`/`executemany` INSERT i `outbox_events` **før** `DELETE`, samme cursor,
   ét `conn.commit()`. Signatur ændres fra `(conn, ids)` til `(conn, rows)` så payloaden
   kan bygges af de rækker vi allerede har hentet. ~15 linjer.

4. [ ] **Unit-test af rækkebyggeren** — `services/transaction-service/tests/unit/test_cleanup_script_outbox.py`.
   Loader scriptet via `importlib` fra `_REPO_ROOT/scripts`, asserterer at payloaden
   parser tilbage som `TransactionDeletedEvent` med korrekte felter, at `event_type` er
   `transaction.deleted`, og at `aggregate_id` matcher tx-id. Ligger i transaction-services
   suite fordi den er i CI-matricen og ejer både `contracts` og DB'en.

5. [ ] **Afstem tx 1119** — engangs-INSERT af én outbox-row med payload bygget af
   ES-dokumentets egne felter (account_id 1, user_id 1, amount 138.00). Rækken findes ikke
   i Postgres længere, så scriptet kan ikke selv finde den. Kører gennem den *rigtige*
   publisher-sti — vi patcher ikke ES direkte, for det ville være præcis den overtrædelse
   vi er ved at lukke. SQL'en gemmes i session-loggen.

6. [ ] **Den durable regel** — `dev-notes/patterns/transactional-outbox.md`, nyt afsnit:
   *scripts der skriver i en services database er deltagere i dens event-kontrakt, ikke
   observatører af den.* Nævn `backfill_category_names.py` som det legitime modstykke
   (den læser fra én DB og publicerer til MQ — ingen skrivning bag om outboxen) så reglen
   ikke læses som "scripts må aldrig røre MQ".

7. [ ] **Filer eval-seed-fundet** — nyt finding + P3-item om at
   `ai-service/tests/eval/es_seed.py` seeder 66 fixtures ind i produktions-indexet.

8. [ ] **Verifikation** — se nedenfor.

## Verification

**Unit** — `make -C services/transaction-service test` grøn (117+ tests + den nye).
**Lint** — `make -C services/transaction-service check` (ruff check *og* format, uden pipe:
tre CI-jobs var røde i sidste uge fordi `| tail` skjulte exit-koden).

**Live e2e, målt før/efter** — den rigtige verifikation, jf. P1-13's erfaring med at måle
mod kørende containere frem for at forudsige:

1. Før: notér `count`/`sum` for konto 1 / juli i både Postgres og ES (53/17 528,17 vs
   54/17 666,17) og fuld id-sæt-diff (67 fantomer).
2. Kør `--execute`. Scriptet sletter de 2 rigtige dubletter (864, 1024).
3. Assertér: `outbox_events` fik 2 nye `transaction.deleted`-rækker, som går
   `pending → published` af sig selv (ingen manuel publish).
4. Assertér: begge id'er har `is_deleted: true` i `transactions_v2` inden for et par
   sekunder.
5. Efter afstemning af 1119: id-sæt-diffen for rigtige brugere er **tom**, og analytics'
   tal for konto 1 / juli matcher Postgres eksakt.
6. Kontrol-assertion: ingen rækker i `transactions_v2` blev markeret slettet ud over de
   forventede — diff'en må ikke svinge den anden vej.

## Risks & rollback

- **Sletning af rigtige data (864, 1024).** Trin 2 fjerner to rigtige rækker og ændrer juni-
  og april-tal med −30,00 og −120,00. De *er* ægte dubletter og det er værktøjets formål,
  men det er en irreversibel mutation af brugerdata. **Kræver eksplicit go før trin 2** —
  alternativet er at verificere mod et selvlavet throwaway-par, som sidste session gjorde
  med budget-rækken. Scriptets JSONL-audit gør genindsættelse mulig, men uden samme id'er.
- **Halv-transaktion.** Hvis INSERT lykkes og DELETE fejler, står der et delete-event for
  en levende række → ES markerer en levende transaktion som slettet. Mitigeret ved at
  begge kører på samme cursor med ét commit; `conn.autocommit = False` er allerede sat.
  Verificeres med kontrol-assertion 6.
- **Payload-drift.** Elimineret ved at importere det rigtige `TransactionDeletedEvent`
  frem for at håndbygge JSON.
- **Rollback**: `git revert` på script-committen. Data-delen kan ikke revertes (ES-
  tombstones er terminale ved design — `is_deleted` er `noop`-guarded mod genoplivning),
  men den bringer read-modellen *tættere* på Postgres, ikke længere væk.

## Outcome

**Shipped 2026-07-26** in 2 code commits (`b0a9c2b7` fix + test, `c5cd9b90` style) plus docs.
All 8 steps done as planned. Real-user phantoms went 1 → **0**.

### What was verified live

Chain proven end-to-end against the running stack, with a throwaway pair created through
the real API (so ES held them as genuinely projected live documents, not hand-seeded ones):

| Assertion | Result |
|---|---|
| Outbox rows written | 3, all `pending → published` by the existing worker, no manual publish |
| Deleted rows in ES | 864, 1024, 1139 → `is_deleted: true` |
| **Survivors untouched** | 860, 1023, 1138 → `is_deleted: false` (control) |
| July, account 1 | ES 17 666,17 → **17 528,17** = Postgres exactly |
| June / April | followed Postgres in lockstep (−30,00 / −120,00) |
| Full id-set diff | 0 real-user phantoms, 0 rows missing in ES |

### Deviations

- **The 138 kr reconciliation turned out not to be the whole job.** Diffing the full id set
  instead of one month found 67 phantoms. 66 had a different cause (eval fixtures) → filed
  as **P3-21**, not absorbed into this plan.
- **Two real duplicates were still in the database** (864, 1024) and the script has no id
  filter, so they were deleted too — with explicit go, after showing the dry-run. That was
  a better verification than the throwaway alone: it proved the fix on production-shaped
  data and removed real double-counting from June and April.
- **Added a rowcount guard that was not in the plan.** While writing `_delete_rows` the
  inverse failure became obvious: outboxing more deletes than the DELETE matched would
  tombstone *live* rows, and `is_deleted` is terminal in ES, so that is as unrecoverable as
  the bug being fixed. Mismatch now rolls back and raises. Covered by a unit test.
- **`scripts/` is outside the lint perimeter** (`PY_SERVICE_DIRS` drives lint/format, and
  the directory is in neither). The file had never been `ruff format`ed and carried an
  unused `import sys`. Formatted in its own commit so the fix diff stays readable. Not
  filed — it belongs with the unwatched-CI decision still pending.
- **The documented invocation did not work.** `uv run python scripts/...` fails: there is no
  root pyproject. Corrected to `uv run --project services/transaction-service`, which is
  also the principled choice, and is what makes importing the real contract class possible.

### Follow-ups spawned

- **P3-21** — eval seed writes into the production index; blocks turning the id-set diff
  into an automated must-be-zero check.
- **P2-25 unchanged.** This plan makes hard-delete event-correct; it does not decide whether
  hard-delete is right. The soft-delete argument is now slightly stronger: with a
  `deleted_at` column the P3-20 class of leak is detectable by comparing counts rather than
  diffing id sets.
- The 66 eval fixtures were left in place, deliberately.
