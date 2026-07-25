---
title: notification-service hardening (close-out) + P2-22 saga-inbox og loose ends
date: 2026-07-25
---

# 2026-07-25 — notification-hardening close-out + P2-22

Dagen dækker to sammenhængende stykker arbejde. Det første
([hardening-planen](../plans/2026-07-25-notification-service-hardening.md)) blev shippet og
merget uden session-log; den mangel lukkes her. Det andet
([P2-22-planen](../plans/2026-07-25-p222-saga-inbox-and-loose-ends.md)) rydder de løse ender
det første efterlod — inklusive den fejl review'et fandt men bevidst ikke rettede.

## Del 1 — notification-service hardening (merget, 23e2d110)

16 commits på `fix/notification-service-hardening`. Scope voksede fra én service til fire
(notification, banking, saga, shared/contracts + frontend), fordi spørgsmålet "skal dette
event blive en notifikation?" besvares med data der produceres tre services opstrøms.

Kerneleverancen: `trigger` på `BankSyncCompletedEvent`, båret på P3-14's sync-claim, så
F1-05's natlige sweep ikke længere notificerer når der intet er at fortælle — mens brugerens
eget klik altid får en kvittering.

Detaljer, deviations og den fulde not-fixed-liste står i planens Outcome-sektion.

## Del 2 — P2-22 + loose ends (denne session, 9 commits)

### Det egentlige fund: platformens dedup-nøgle duer ikke for saga-kommandoer

P2-22 var beskrevet som "tilføj den inbox-guard konventionerne foreskriver". To ting i koden
ændrede opgaven:

1. **banking-service havde allerede `processed_events`** (migration 001, brugt af
   `account_projection_consumer`). Ingen migration nødvendig — backloggen antog en.
2. **`ConsumerBase`'s nøgle kan ikke bruges.** Den deduplikerer på
   `payload["correlation_id"]`. saga-service lægger ikke `correlation_id` i
   kommando-body'en (`_publish_step_command` bygger et rent dict), og den værdi den sætter på
   outbox-rækken er `saga.correlation_id` — **den samme for alle tre trin**. Dedup på den
   ville gøre trin 2 til en dublet af trin 1 og standse sagaen tavst.

Nøglen blev `(saga_id, step_name)`. Den er sikker fordi orchestratoren aldrig genudsender et
*eksekverings*-trin: `handle_reply` kræver `STARTED` + navne-match og rykker frem, og timeout
går til kompensation. Det ene sted noget genudsendes er `_handle_stale_compensation`, som kun
rammer `rollback_import` — idempotent i forvejen.

Det forklarer også hvorfor P2-01 carvede netop disse to consumers ud af `ConsumerBase`. Den
carve-out var ikke vilkårlig, og grunden holder stadig.

### To designvalg der er nemme at få forkert

- **Dubletten skal svare.** Årsagen til redeliveryen er typisk et tabt reply. Ack'er man uden
  at svare, hænger sagaen til timeout og går i kompensation — man bytter en
  spøgelsesnotifikation for en fejlet saga.
- **Inbox-rækken skal ligge i handlerens egen transaktion.** Committes den separat, koster
  idempotensen retry-evnen: en handler der rejser efter inbox-commit men før effekt-commit
  ville aldrig køre igen.

### Hvad der bevidst *ikke* blev dedupliceret

`bank_fetch_transactions` bærer hele fetchen i sit reply. En skip-and-ack guard ville svare
uden items → sagaen importerer 0 → syncen taber transaktioner i stilhed. Værre end det
gentagne EB-kald en redelivery koster. `bulk_import` har samme form (reply bærer
`imported_ids`, som kompensationen har brug for) → **P2-23**, stored reply.

Begge domme står nu som docstrings i koden, ikke kun i backloggen.

### Sidefund: banking-service's CI-job kunne aldrig køre sine tests

Undervejs viste det sig at `pytest tests` ikke kunne *collecte* i CI: `Settings` kræver
`DATABASE_URL`, workflowet sætter den ikke, og banking var den ene service uden
`tests/conftest.py`. Fejlen var maskeret, fordi `ruff format --check` fejlede tidligere i
samme job og afbrød det — hardeningens formateringsfix (d5630a6e) afdækkede den.

P2-14 registrerede banking som dækket af CI siden 2026-07-07. Rækken sagde "done", mens
jobbet ikke kunne udføre en enkelt test.
[Finding skrevet](../findings/2026-07-25-banking-ci-could-not-collect.md).

Samtidig: de tre shared-pakker var slet ikke i CI, og **alle tre** fejlede
`ruff format --check` (planen forventede kun `contracts`). De havde også stadig den gamle
`[project.optional-dependencies] dev`-form uden `ruff`, så `uv sync --dev` installerede
intet værktøj og `uv run ruff` fejlede med "Failed to spawn" — migreret til
`[dependency-groups]` som services bruger.

## Verifikation

| Suite | Resultat |
|---|---|
| banking-service | 66 passed (60 før; +6 P2-22-tests) |
| notification-service | 90 passed, `make check` grøn |
| transaction-service | 215 passed |
| shared/contracts · messaging · auth | 56 · 45 · 28 passed, lint+format+bandit grønne |

**Mutation-checket** (planens step 2): en per-delivery-unik nøgle brister
redelivery-testene, og `saga_id` alene brister "to trin i samme saga kører begge". Begge
mutationer verificeret manuelt — testene består ikke vakuøst.

Alle fire CI-steps for de tre shared-pakker er kørt lokalt med præcis de kommandoer jobbet
kalder, inkl. `bandit -ll -ii` (0 findings ved den tærskel; de 3 Low-severity findings i
`messaging` er under den, som for services).

**Live-verifikation gennemført** (planens step 9, fuld tabel i planens Outcome). Kernen:
redelivery af samme `mark_sync_complete` gav 0 nye notifikationer, 0 nye outbox-rækker og
1 uændret inbox-række, mens `saga_reply.dlq` indeholdt præcis 2 replies — én per levering,
altså svarede dublet-stien også. Step 7's `.value`-skrivning verificeret mod rigtig Postgres
i en rullet-tilbage transaktion (`'scheduled'`/`'manual'`, ikke `'SyncTrigger.X'`).

Det live-testen *ikke* beviste: saga-siden var syntetisk, så orchestratorens accept af
dublet-replyet blev ikke observeret, og ingen ægte EB-sync blev kørt (ingen JWT tilgængelig).

## Gotchas værd at huske

- **`bandit`s output-blokke er nemme at fejllæse.** Jeg troede først `messaging` havde 3
  HIGH-findings; "High: 3" stod i *confidence*-blokken, ikke severity. `-ll -ii` gav
  "No issues identified", exit 0. Læs blok-headeren, ikke bare tallet.
- **`uv sync --dev` installerer PEP 735 `[dependency-groups]`, ikke
  `[project.optional-dependencies]`-extras.** Symptomet er ikke en fejl om manglende
  dependency, men `error: Failed to spawn: ruff` — hvilket læses som en PATH-fejl.
- **banking-service kan nu testes bart** (`pytest tests`, ingen env, ingen `PYTHONPATH`).
  Den incantation hardeningens plan dokumenterede som gotcha er overflødig.

## Åbne ender efter i dag

- **Testartefakter i dev-DB'en**: 1 falsk sync-notifikation til user 1 (+ outbox- og
  inbox-række), alle identificerbare på `p222-smoke`-præfikset. Ikke ryddet op.
- **Ægte end-to-end sync** mangler stadig som observation (ingen JWT/login-helper); den
  ville også vise orchestratorens accept af et dublet-reply.
- **P2-23** stored reply for `bulk_import` (+ ville også låse op for at guarde
  `bank_fetch_transactions`).
- **P2-24** delt intern-API-klient — owner-lookup findes i tre hånd-rullede kopier.
- **P2-21 / P3-17** k8s-manifest-drift og migrations-rækkefølge — uberørt, som planlagt.
- **P3-18** notification-retention + præferencemodel; gate før rigtig SMTP.
