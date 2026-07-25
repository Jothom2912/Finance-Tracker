---
title: P2-22 — inbox guard på saga-command consumers + loose ends fra notification-hardening
date: 2026-07-25
status: open
backlog-items: [P2-22, P3-09]
related:
  - plans/2026-07-25-notification-service-hardening.md
  - patterns/idempotent-consumers.md
  - decisions/2026-07-17-scheduler-pattern-worker-loop.md
---

# P2-22 — inbox guard på saga-command consumers + loose ends fra notification-hardening

## Goal

Gør `saga.cmd.mark_sync_complete` én-gangs-virkende, så en redelivered saga-kommando ikke
kan producere et andet `BankSyncCompletedEvent` og dermed en spøgelsesnotifikation
("ingen nye transaktioner") som `source_key`-dedup ikke kan absorbere. Samtidig lukkes de
fire småting review'et af notification-hardeningen efterlod, og de tre *øvrige*
saga-command-handlers får en **skreven** dom (dedup / ikke-dedup / kan ikke dedupes uden
stored reply) i stedet for en åben antagelse.

Færdig når: banking-suiten dækker redelivery-scenariet, en redelivered
`mark_sync_complete` giver præcis **én** outbox-række og **stadig** et success-reply, og
live-flowet viser at en gentaget kommando ikke skaber en ny notifikation.

## Context

P2-22 blev fundet under review af notification-service-hardeningen
([plan](2026-07-25-notification-service-hardening.md), step 8b / not-fixed-listen).
`_handle_mark_sync_complete` rydder sync-claimet og skriver outbox-rækken i **én**
transaktion — det er korrekt — men intet deduplikerer *kommandoen*. Fejler reply-publish
efter commit (eller tabes ACK'en), læser redeliveryen et nu-NULL `sync_trigger` → falder
tilbage til `MANUAL` → udsender et **andet** `BankSyncCompletedEvent` med frisk
`correlation_id` → notification-service beregner en anden `source_key` → unique-constraint
kan ikke absorbere det. Resultat: en spøgelsesnotifikation, og F1-05's undertrykkelse af
stille scheduled syncs er slået ud på præcis den sti.

Fejlen er **pre-existing** — den dobbelt-notificerede også før trigger-arbejdet. Suppression
gjorde den bare synlig.

To ting undersøgt i koden inden planen, som ændrer den fra det backloggen antog:

1. **Banking-service har allerede `processed_events`.** Tabellen kom i migration
   `001_initial_schema.py`, modellen er `app/models/processed_events.py`, og
   `account_projection_consumer.py` bruger den med præcis det idiom vi skal genbruge
   (fast-path check → mark i samme transaktion → `IntegrityError` på commit = benign race).
   **Ingen migration er nødvendig.** Kolonnen er `correlation_id String(255)` — rigelig plads
   til en sammensat nøgle.

2. **Platform-standardnøglen virker ikke for saga-kommandoer.** `ConsumerBase`'s
   `InboxDeduplicator` deduplikerer på `payload["correlation_id"]`. Saga-kommandoer har ikke
   noget per-message `correlation_id` i body'en: orchestratoren bygger payloaden som et rent
   dict (`_publish_step_command`) og sætter `correlation_id` på *outbox-rækken* — og den værdi
   er `saga.correlation_id`, altså **den samme for alle tre trin i samme saga**. Dedup på den
   ville behandle trin 2 som en dublet af trin 1. Det er den egentlige grund til at P2-01
   carvede disse consumers ud, og den grund gælder stadig.

   Nøglen skal derfor være **`(saga_id, step_name)`**, som er sagaens naturlige
   trin-identitet. Det er sikkert her, fordi orchestratoren **aldrig genudsender et
   eksekverings-trin**: `handle_reply` kræver `status == STARTED` og
   `current_step.name == step_name` og rykker derefter frem; timeout går til *kompensation*
   (`_handle_stale_execution`), ikke til retry af trinnet. Det eneste sted en kommando
   genudsendes er `_handle_stale_compensation`, og det rammer kun `rollback_import`.

Bemærk også en skema-divergens der modsiger en kommentar i repoet: transaction-service's
migration 007 kalder sit skema "standardised across the platform"
(`message_id String(36)` + `event_type`), men banking bruger
`correlation_id String(255)` uden `event_type`. Ingen af dem er forkerte; påstanden om
standardisering er. Rettes i pattern-doc'en (step 8), ikke i skemaet — en migration for
kosmetik på en tabel to consumers er afhængige af er ikke værd at betale.

## Non-goals

- **Ingen ændring af saga-semantik.** Orchestrator, trin-rækkefølge, kompensation,
  timeout-håndtering og reply-kontrakten røres ikke. Kun deltager-siden bliver idempotent.
- **`bank_fetch_transactions` bliver bevidst IKKE dedupliceret.** Dens reply bærer
  `result_data.items` — hele fetchen. En dedup-sti der ack'er uden at genskabe items ville
  sende et tomt reply → sagaen importerer 0 → syncen taber transaktioner i stilhed. Det er en
  værre fejl end et gentaget EB-kald. Skrives som kommentar i koden (step 3), ikke som kode.
- **`bulk_import` får ikke stored-reply-behandling i denne plan** (se step 3 — bliver nyt
  backlog-item). Den er data-sikker i forvejen via P2-09-dedup; det åbne hul er alene
  `imported_ids`, som er tom ved redelivery.
- **Ingen retention/purge af `processed_events`.** Rækkerne akkumulerer som i dag; hører under
  P2-20's opt-in purge, ikke her.
- **Notifikationstekster, feed-API, bell-UI og suppression-reglen ændres ikke.** Denne plan
  fjerner en spøgelsesrække; den ændrer ikke hvad en ægte række siger.
- **P3-09 (`event_id` på `BaseEvent`) løses ikke** — den ville gøre denne nøgle unødvendig på
  sigt, men er en kontraktændring på tværs af alle services.

## Steps

1. [ ] **Inbox guard på `_handle_mark_sync_complete`** —
   `banking-service/app/workers/saga_command_consumer.py`.
   - Ny modul-konstant + helper: `_step_key(saga_id, step_name) -> str` →
     `f"{saga_id}:{step_name}"`, og `_is_duplicate(session, key)` /
     `_add_inbox_row(session, key)` i samme form som `account_projection_consumer`
     (samme `consumer_name = QUEUE_NAME`).
   - I `_handle_mark_sync_complete`: efter `async with async_session_factory()`, **før**
     nogen mutation → `if await self._is_duplicate(session, key): return {"success": True}`.
     Returværdien er vigtig: en dublet skal **stadig** give et reply, ellers står sagaen for
     evigt. Dubletten er per definition typisk *forårsaget* af et tabt reply.
   - Inbox-rækken tilføjes til **samme session** som claim-ryddet og outbox-rækken, før
     `session.commit()`. Det er hele pointen: rejser handleren før commit, findes rækken
     ikke, og consumerens egen `_republish`-retry kan køre igen uafhængigt. Idempotens må
     ikke koste retry-evnen.
   - Pak `session.commit()` i `except IntegrityError` → rollback, log benign race, returnér
     `{"success": True}` (to samtidige deliveries).
   - Diff-form: ~35 linjer i én fil, ingen migration, ingen kontraktændring.

2. [ ] **Tests for guarden** — `banking-service/tests/unit/test_saga_command_consumer.py`.
   - Redelivery af samme `(saga_id, step_name)` → **én** outbox-række, og andet kald
     returnerer stadig `success: True`.
   - P2-22-historien end-to-end på handler-niveau: kør handleren, ryd claimet (som første
     kald gør), kør igen → **ingen** ny `BankSyncCompletedEvent`. Uden guarden giver dette
     to events med forskellig `correlation_id` — testen skal fejle på `main` uden step 1.
   - `IntegrityError`-race-stien (exists-check ren, INSERT afvist).
   - To *forskellige* trin i samme saga → **begge** kører (beviser at nøglen ikke er
     `saga_id` alene — den fejl ville stoppe hele sagaen og er let at lave).
   - Mutation-check som i hardeningens step 7: gør nøglen per-delivery-unik og bekræft at
     dedup-testen fejler, så den ikke består vakuøst.

3. [ ] **Skriv dommen over de tre øvrige handlers** — kommentarer + nyt backlog-item, ingen
   adfærdsændring.
   - `bank_fetch_transactions` (banking): kommentar om at dedup her er *forkert* og hvorfor
     (reply bærer hele fetchen). Rene læsninger + EB-kald; redelivery er spild, ikke skade.
   - `_handle_rollback_import` (transaction): allerede idempotent
     (`TransactionNotFoundException` sluges bevidst) — og det er den *eneste* kommando
     orchestratoren faktisk genudsender (`_handle_stale_compensation`). Kommentar der
     knytter de to fakta sammen.
   - `_handle_bulk_import` (transaction): data-sikker via P2-09, men reply'ets `imported_ids`
     er **tom** ved redelivery (alt dedupes som duplicates) → fejler sagaen bagefter, har
     kompensationen intet at rulle tilbage, og de importerede rækker bliver liggende.
     Kræver *stored reply*, ikke almindelig dedup → **nyt item P2-23**, med vinduet skrevet
     ned. Kommentar i koden der peger på det.

4. [ ] **Slet død `clear_sync_claim`** — `banking-service/app/application/ports/outbound.py`
   + `app/adapters/outbound/postgres_bank_connection_repository.py`. Nul callers
   (verificeret), ingen tests. Claimet frigives ved ORM-mutation i consumeren. To
   implementeringer af samme regel hvoraf den ene er falsk er værre end ingen.

5. [ ] **`aclose()` på en port der ikke erklærer den** — notification-service.
   `notification_consumer.py:73` kalder `aclose()` i en `finally` på owner-porten;
   erklæres den ikke på porten, giver en substitueret implementation `AttributeError` under
   shutdown og maskerer den *rigtige* fejl. Fix: erklær `aclose()` på porten (arkitektonisk
   ærligt — lifetime er en del af kontrakten), ikke `getattr`-workaround.

6. [ ] **Shared-pakkerne ind i CI** — `.github/workflows/ci.yml`.
   `services/shared/contracts` fejler `ruff format --check` **lige nu** (2 filer, F2-03-kode)
   uden at CI fanger det, fordi matrixen kun indeholder de 12 services. En shared-pakke der
   brækker rammer alle 12 — det er den værste ting at have udenfor CI.
   - Kan ikke være matrix-entries: jobbet har et bandit-step der hard-fejler uden `app/`.
     Nyt separat job `shared-packages` med egen matrix over `contracts`/`messaging`/`auth`:
     `uv sync --dev` → `ruff check .` → `ruff format --check .` → `bandit -r <pkg> -ll -ii`
     → `pytest tests`.
   - Separat commit: `ruff format` på de to filer, så formateringsstøj ikke blandes med
     CI-ændringen.

7. [ ] **(Droppable) Type `sync_trigger` som `SyncTrigger`** i banking-porten og
   -entiteten i stedet for `str`. I dag round-trippes enum → str → DB → str → enum, så en
   forkert værdi type-checker og degraderer stille til MANUAL (kun opdaget af
   `_parse_sync_trigger`s warning, tilføjet i hardeningen). Rigtigt kald, men det er
   P3-14-kode og udvider diffen. **Tages kun hvis step 1–6 er grønne** — ellers eget item.

8. [ ] **Docs** — separat commit, ingen kode.
   - `patterns/idempotent-consumers.md`: ny sektion "saga-kommandoer er undtagelsen" —
     hvorfor `correlation_id` ikke duer som nøgle, at `(saga_id, step_name)` er den
     korrekte, hvorfor inbox-rækken skal ligge i handler-transaktionen (retry-evne), og at
     en dedupliceret kommando **stadig skal svare**. Ret samtidig påstanden om et
     "standardiseret" `processed_events`-skema — de to varianter dokumenteres som de er.
   - `architecture/services/banking-and-saga-services.md`: guarden + nøglevalget.
   - `backlog/BACKLOG.md`: P2-22 → done; nyt **P2-23** (stored reply for `bulk_import`);
     nyt **P3-19** (delt intern-API-klient i `services/shared` — owner-lookup findes i tre
     hånd-rullede kopier i notification-, goal- og banking-service med tre forskellige
     fejl-taksonomier; pooling- og auth-klassifikations-vindingerne fra hardeningens step 5
     nåede kun den ene).
   - **Manglende session-log for 2026-07-25** (`sessions/` stopper ved 2026-07-20):
     hardeningen var fire services og 16 commits og har ingen. Skrives sammen med denne
     plans close-out, så begge dages arbejde er dækket.
   - `00-INDEX.md`: denne plan + session-loggen.

9. [ ] **Verification.**

   ```bash
   make -C services/notification-service check && make -C services/notification-service test
   make -C services/transaction-service test
   make -C services/shared/contracts test        # + ruff format --check .
   make test-e2e
   ```

   banking-service har **ingen `pyproject.toml`** (kun requirements.txt), så `uv run pytest`
   virker ikke der. Brug incantationen fra hardeningens follow-ups:

   ```bash
   cd services/banking-service && PYTHONPATH=../shared/contracts:../shared:. \
     uv run --python 3.11 --with-requirements requirements.txt \
     --with pytest --with pytest-asyncio --with aiosqlite pytest tests
   ```

   `--python 3.11` er påkrævet (`psycopg2-binary==2.9.10` har intet wheel til nyere
   interpretere).

   **Live** — den del tests ikke kan bevise (jf. eksamensnoten om at en unit-testet handler
   ikke er en fungerende event-sti):
   1. `docker compose up -d`; bekræft at **den byggede** `banking-service`-image indeholder
      step 1's kode (`docker compose exec banking-saga-consumer grep -c _step_key ...`) —
      `compose build banking-service` bygger ikke dens workers, og en falsk grøn live-test
      her er præcis den fælde der er dokumenteret to gange i disse noter.
   2. Kør en manuel sync til ende → **én** notifikation.
   3. Genudsend den samme `saga.cmd.mark_sync_complete` (samme `saga_id` + `step_name`) med
      `rabbitmqadmin publish` → **ingen** ny række i `notifications`, **ingen** ny outbox-række,
      og consumer-loggen viser dublet-skip.
   4. Bekræft at saga'en stadig er `completed` — beviser at dubletten svarede i stedet for at
      efterlade orchestratoren hængende.

## Risks & rollback

| Risk | Detection | Rollback |
|---|---|---|
| Nøglen for bred (fx `saga_id` alene) → trin 2 og 3 dedupes som dubletter af trin 1, sagaen dør stille | Step 2's "to forskellige trin i samme saga"-test | revert step 1 (én fil) |
| Guarden dræber consumerens egen retry, fordi inbox-rækken commit'es uafhængigt af effekterne | Rækken ligger i *samme* session/commit; en handler der rejser før commit efterlader ingen række — dækket af retry-testen | revert step 1 |
| En dublet ack'er uden reply → sagaen hænger til timeout og går i kompensation | Live step 4 (saga = `completed`); dedup-stien returnerer eksplicit `{"success": True}` | revert step 1 |
| `processed_events` vokser uden purge | Kendt og accepteret; samme vilkår som de to eksisterende consumers | — (P2-20) |
| Step 6 gør CI rød på tværs af de tre shared-pakker på én gang | Kør de tre kommandoer lokalt før commit; `contracts` er kendt rød og fikses i egen commit først | revert CI-jobbet, behold formateringsfixet |
| Step 4 sletter en metode med en caller jeg har overset | `grep -rn clear_sync_claim` viste kun deklaration + impl; suiten kører efter | revert (ren sletning) |

Hvert step er egen commit. Step 1+2 hører sammen (fix + bevis) men er stadig revertable som
par uden at røre step 3–8.

## Outcome (fill in when done)

<!-- udfyldes ved close-out: deviations, follow-ups, faktiske suite-tal -->
