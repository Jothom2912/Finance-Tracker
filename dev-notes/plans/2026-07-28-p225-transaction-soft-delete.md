---
title: "P2-25: transaction soft-delete + gone-vs-not-yet i categorization-write-backen"
date: 2026-07-28
status: done
backlog-items: [P2-25, P3-37]
related:
  - ../findings/2026-07-25-transaction-hard-delete-categorized-dlq.md
  - ../findings/2026-07-25-cleanup-script-desyncs-read-model.md
  - ../decisions/2026-07-16-p209-dedup-semantics.md
  - 2026-07-17-p316-goal-soft-delete.md
---

# P2-25: transaction soft-delete + gone-vs-not-yet i categorization-write-backen

## Goal

`transactions` får en `deleted_at`-kolonne, og `DELETE /api/v1/transactions/{id}` sætter den
i stedet for at fjerne rækken. Derefter — og først derefter — kan
`categorized_consumer.py:73-76` skelne "ikke committet endnu" (retry er rigtigt) fra "slettet
for altid" (retry er meningsløst), som er den observerede DLQ-bug.

Done når: (a) en slettet transaktion er usynlig på alle læse-stier og i dedup, præcis som i dag;
(b) en `transaction.categorized` for en slettet transaktion acker med én INFO-linje og lander
**ikke** i `transaction_service.transaction_categorized.dlq`; (c) rækken kan stadig findes i
Postgres med `deleted_at` sat. Målt på en kørende stak, ikke kun i tests.

## Context

To fund fra 2026-07-25, som kun bider i kombination
([finding](../findings/2026-07-25-transaction-hard-delete-categorized-dlq.md)):

1. transaction-service hard-deleter (`postgres_transaction_repository.py:171-182`), mod
   CLAUDE.md's egen anti-pattern-liste. goal-service fik soft-delete i P3-16; transaktioner —
   den mest audit-relevante entitet i systemet — fik det ikke.
2. `_TransactionNotFoundYet` konflaterer to tilstande. tx 1133 blev oprettet, kategoriseret og
   slettet mid-flight → 5 retries med 1/2/4/8/16 s backoff på en `prefetch=1`-consumer → DLQ.
   `PoisonMessageError` bruges allerede i samme fil (`:66`), så mekanikken findes — men med en
   hard delete er "endnu ikke" og "aldrig igen" den samme observation, så grenen kan ikke skrives.

Det er derfor rækkefølgen er bundet: P3-37 (migrationen + `deleted_at IS NULL`-prædikatet) er
ikke et selvstændigt item, den er udmøntningen af beslutningen i P2-25. De landes samlet;
migrationen alene har ingen værdi, og consumer-fixet alene er umuligt.

**Blast radius er mindre end finding'en oprindeligt frygtede, og det er målt:**

- **ES-read-modellen skal ikke røres.** `transaction.deleted` konsumeres allerede af
  `analytics.transactions` → `projections.py:94-98` → `transaction_store.py:208-224`, som sætter
  `is_deleted: true` (scripted upsert, `scripted_upsert=True`, så en delete der ankommer før sin
  create stadig laver en tombstone). Flaget er envejs: alle tre update-scripts noop'er på
  `is_deleted == true` (`transaction_store.py:31,58,84`).
- **Analytics filtrerer allerede.** `_base_filters` (`query_store.py:149-168`) har
  `{"term": {"is_deleted": False}}`, og hver eneste liste/aggregering går gennem den — inkl.
  `hybrid_search_transactions`, som gentager termen som kNN-prefilter (`:514,547,577`).
- **Ingen anden service læser transaktioner fra en DB.** budget-service læser forbrug over HTTP
  fra `/analytics/overview`; ai-service ligeså; analytics' backfill kalder transaction-services
  egen liste-API — så alle tre arver filteret gratis.
- **Kun to køer binder `transaction.*` overhovedet**, og `analytics.embeddings` ignorerer
  eksplicit `transaction.deleted` (`embedding_consumer.py:54-55`).

Ændringen er altså indeholdt i transaction-service plus ét maintenance-script.

## Beslutninger truffet før planen (2026-07-28)

**1. Dedup ekskluderer slettede rækker.** En soft-slettet række må ikke blokere re-import.
Både `find_existing_dedup_keys` (`:188-235`) og `find_existing_external_ids` (`:237-268`) får
`deleted_at IS NULL`, og den partielle unique-index `uq_transactions_account_external_id`
udvides med `AND deleted_at IS NULL` — ellers optager tombstonen stadig sin `(account_id,
external_id)`-plads og re-import af en id-bærende række rammer en unique-violation.
*Trade-off:* re-import giver et nyt id, og det gamle bliver liggende som tombstone. Til gengæld
er dagens observerbare adfærd bevaret eksakt — soft-delete bliver usynlig for alt andet end
auditsporet. Alternativet (slettet = "set og fravalgt") gør delete til et permanent, usynligt
importfilter brugeren ikke kan fortryde, og ville bryde rollback→re-import.
Genoplivning (clear `deleted_at`) er afvist, fordi ES-guarden er terminal: read-modellen ville
aldrig få rækken tilbage, så vi ville skulle rive den envejs-garanti ned først.

**2. Saga-kompensationen `rollback_import` bliver soft.** Den går gennem samme use case
(`saga_command_consumer.py:199-248` → `service.delete_transaction`) og får ingen særvej.
*Trade-off:* rækker der aldrig burde have eksisteret akkumuleres. Accepteret, fordi to
slette-semantikker er dyrere at holde styr på end nogle tombstones, og fordi auditsporet på en
*fejlet* import faktisk er værd at have. Re-import efter rollback virker i kraft af beslutning 1.

**3. Consumeren acker — den DLQ'er ikke.** Finding'ens forslag var `PoisonMessageError` for en
slettet række. Det er forkert: `PoisonMessageError` sender til DLQ
(`shared/messaging/messaging/consumer.py:213-220`), og en kategorisering for en slettet
transaktion er et *forventet* race, ikke en fejl der kræver menneskelig opmærksomhed. At DLQ'e
den ville bevare præcis det problem finding'en beskriver — "en DLQ der samler godartede
beskeder holder op med at være et signal". Grenen returnerer i stedet stille, som
duplikat-grenen på `:69-71` gør.

## Non-goals

- **Ingen kontrakt-ændring.** `TransactionDeletedEvent` (`contracts/events/transaction.py:134-143`)
  beholder sit felt-sæt og `event_version = 1`. Consumere ser ingen forskel.
- **Ingen ændring i analytics eller ES** — hverken mapping, projektion eller filtre.
- **Intet restore/undelete-endpoint** og ingen purge/retention-jobs. Tombstones bliver liggende;
  hvad der skal ske med dem på sigt er ikke dette items beslutning.
- **`planned_transactions` røres ikke** — den har allerede sin egen `is_active`-deaktivering
  (`models.py:122`), som er en anden ting, og at forene de to er ikke i scope.
- **Ingen adfærdsændring der er synlig for frontend eller gateway.** Lister, totaler, søgning,
  overblik og budget-forbrug skal give nøjagtigt de samme tal efter som før.
- **`_get_transaction` i consumeren får bevidst *ikke* filteret** — den skal kunne se den
  slettede række for at kunne skelne. Det er hele pointen.

## Steps

Commit per fase.

1. [ ] **Migration 013 + model.** `migrations/versions/013_add_transaction_soft_delete.py`
   (down_revision `012`): `add_column("transactions", deleted_at TIMESTAMP WITH TIME ZONE NULL)`;
   drop og genskab `uq_transactions_account_external_id` med
   `postgresql_where=text("external_id IS NOT NULL AND deleted_at IS NULL")`. `downgrade` gør det
   omvendte. `app/models.py`: `deleted_at: Mapped[datetime | None]` på `TransactionModel` (samme
   form som `goal-service/app/models.py:25`) + `__table_args__`-index opdateret så model og
   migration er enige. Verifikation: `tests/migrations/test_alembic_upgrade.py`.

2. [ ] **Læse-prædikater i repositoriet.** `postgres_transaction_repository.py`:
   `deleted_at.is_(None)` i `find_by_id` (`:55`), i `_filter_clauses` (`:86` — den ene definition,
   som filens egen docstring insisterer på, så liste og total ikke kan divergere), i `update`
   (`:150`) og i begge dedup-queries (`:188`, `:237`). `delete` (`:171`) bliver
   `model.deleted_at = func.now()` i stedet for `session.delete(model)`, stadig scoped på
   `(id, user_id, deleted_at IS NULL)` → anden DELETE giver `False` → 404, som goal-service.
   Sanity-grep før commit: `grep -n 'select(TransactionModel)' -r services/transaction-service/app`
   skal kun efterlade consumerens bevidst ufiltrerede `_get_transaction` og
   `maintenance/backfill_subcategory_name.py`.

3. [ ] **Tests for lag 2.** Integration (`tests/integration/`): en slettet række er væk fra
   `find_filtered` *og* `count_filtered` (samme kald, så en manglende total afsløres);
   `find_by_id` → `None`; re-import af samme dedup-nøgle efter delete opretter en ny række;
   samme for en `external_id`-bærende række (bevis at den partielle index ikke rammer).
   Unit: `delete_transaction` emitterer stadig `TransactionDeletedEvent` i samme UoW.

4. [ ] **Consumerens gone-vs-not-yet.** `categorized_consumer.py:73-76` bliver tre grene:
   række findes og `deleted_at is None` → som i dag; række findes med `deleted_at` sat →
   `logger.info("Transaction %s deleted — categorization moot", …)` + `return` (ack, ingen DLQ);
   række findes ikke → uændret `_stale_backoff` + `_TransactionNotFoundYet`. Test: alle tre
   grene, hvor den midterste asserter at `_stale_backoff` **ikke** kaldes — at den ikke sover
   16 s på en `prefetch=1`-consumer er halvdelen af udbyttet.

5. [ ] **`scripts/cleanup_pg_duplicates.py`.** `DELETE FROM transactions WHERE id = ANY(%s)`
   (`:217`) → `UPDATE transactions SET deleted_at = now() WHERE id = ANY(%s) AND deleted_at IS NULL`.
   P3-20's outbox-række og rowcount-guard i samme transaktion beholdes uændret. Uden dette trin
   ville scriptet være den eneste tilbageværende hard delete, altså præcis den invariant vi lige
   har indført, brudt af repoets eget værktøj.
   Eksisterende dækning: `tests/unit/test_cleanup_script_outbox.py`.

6. [ ] **Verifikation** (se næste sektion) — før docs.

7. [ ] **Docs.** Decision-note `decisions/2026-07-28-transaction-soft-delete.md` (de tre
   beslutninger ovenfor med deres trade-offs); backlog-rækker P2-25 og P3-37 → `done 2026-07-28`
   med link hertil; finding'en → `status: resolved`, `resolved-by`; `STATUS.md` og `00-INDEX.md`.
   `make notes-check` før commit.

## Verification

Statisk, lokalt (transaction-service er på uv, så alle tre virker):

```
make -C services/transaction-service test
make -C services/transaction-service lint
make -C services/transaction-service typecheck   # på gaten siden P2-31
```

Kørende stak — det statiske beviser ikke nogen af de tre Done-kriterier:

1. `docker compose up -d transaction-service analytics-service categorization-service` +
   workers; `alembic upgrade head` og **verificér at kolonnen findes**
   (`\d transactions` → `deleted_at`), ikke kun at exit-koden er 0 (CLAUDE.md's egen fælde).
2. Opret en transaktion → noter `total_count` på listen → `DELETE` → assert: `GET` giver 404,
   rækken er væk fra listen, `total_count` er faldet med præcis 1, og rækken *findes* i Postgres
   med `deleted_at` sat.
3. `/analytics/overview` for samme konto/periode før og efter: differencen skal være rækkens
   beløb og intet andet. ES: dokumentet er `is_deleted: true`.
4. **Reproducér DLQ-buggen.** Tøm `transaction_service.transaction_categorized.dlq`; slet en
   transaktion; publicér en `transaction.categorized` med dens id på `finans_tracker.events`.
   Assert: DLQ'en er stadig tom, én INFO-linje i workerens log, og ingen 16 s backoff.
   **Kør kontrollen også**: samme publish med et id der aldrig har eksisteret skal *stadig*
   retry'e og DLQ'e — ellers har vi lukket grenen frem for at dele den. (Samme lektie som
   `make verify-typecheck-gate` i P2-31/P3-23: mål både treatment og kontrol.)
5. Re-importér den CSV der oprettede den slettede række: den skal komme tilbage med et nyt id.

`make test-e2e` til sidst.

## Risks & rollback

- **En overset læse-sti lækker tombstones.** Værste udfald: en slettet transaktion dukker op i
  én visning. Fanget af grep'et i trin 2 og af `total_count`-assertionen i trin 3 —
  `_filter_clauses` er netop bygget så liste og total ikke kan divergere.
- **Dedup-regressionen er den dyre.** Glemmes `deleted_at IS NULL` i `find_existing_external_ids`,
  fejler re-import med en unique-violation der ligner en saga-fejl. Derfor har trin 3 en test
  specifikt for den id-bærende sti, ikke kun den fuzzy.
- **Den partielle index genskabes.** På et stort `transactions` er drop+create ikke gratis;
  på nuværende volumen (lave tusinder) er det irrelevant, men migrationen bør bruge
  `CREATE INDEX CONCURRENTLY` hvis den nogensinde køres mod en rigtig produktionstabel — ikke
  gjort her, og det noteres i migrationens docstring frem for at blive glemt.
- **Rollback:** `alembic downgrade -1` (kolonnen droppes, index genskabes i sin gamle form) +
  `git revert` af prædikat-commit'en. Rækker slettet i mellemtiden er *ikke* genskabelige som
  hard-deletes — de bliver synlige igen. Det er den rigtige retning for et fejlgreb, men det skal
  siges højt: en downgrade af dette item genopliver data.
- **Consumer-grenen kan skjule en ægte fejl.** Hvis `deleted_at` af en eller anden grund sættes
  bredt (fx et fejlagtigt script), acker consumeren nu stille i stedet for at larme. INFO-linjen
  er det eneste spor — derfor er den formuleret med transaction-id, ikke som en generisk "skipped".

## Outcome

**Landet 2026-07-28 i fem commits**, én per fase:
`762e6c5b` migration 013 + model, `4deb9dac` prædikaterne i repositoriet, `9a578fac` de ni
integrationstests, `3df1d778` consumerens tredje gren, `2b59e77f` cleanup-scriptet.
[Decision-note](../decisions/2026-07-28-transaction-soft-delete.md).

Alle tre Done-kriterier målt på kørende stak, ikke kun i tests: (a) slettet række usynlig på
listen, i `total_count`, i `find_by_id`, i ES (`is_deleted: true`) og i `/analytics/overview`
(500,00 → 0,00 — præcis rækkens beløb); (b) en `transaction.categorized` for den slettede række
acker med én INFO-linje og lader DLQ'en stå på 2; (c) rækken findes i Postgres med `deleted_at`
sat. Kolonnen og det narrowede index aflæst i `\d transactions`, ikke kun exit-kode 0.
Re-import gav et nyt id, begge rækker i tabellen. `make test-e2e` 24 passed, 195 unit +
69 integration grønne, lint og typecheck rene.

### Hvad målingen rettede i planen

**1. Consumer-grenen fixer ikke DLQ-buggen — soft-delete gør.** Planen (og finding'en) tilskrev
DLQ-fixet grenen i trin 4. Kontrollen siger noget andet: med grenen fjernet, men migration og
prædikater på plads, fejler kun *én* af klassens fire tests. Rækken *findes* nu, så
`_get_transaction` returnerer den, og der backes aldrig off. Grenens egen værdi er snævrere og
stadig værd at have: en tombstone må ikke få sine kategoriseringsfelter overskrevet, og skippet
skal efterlade et spor. Det står nu i testklassens docstring, så den ikke læses som bevis for
noget den ikke viser.

**2. Trin 5 var større end "ét sed-udtryk".** Planen nævnte kun `DELETE` → `UPDATE` i
`_delete_rows`. Men `_find_duplicates` filtrerede heller ikke, og efter soft-delete er det en
ægte bug: en tombstone og dens legitime re-import danner en "gruppe", og da tombstonen har det
laveste id ville den blive *beholdt* — scriptet ville slette den levende række. Det ville
samtidig bryde den idempotens scriptets egen docstring lover, fordi et andet gennemløb ville
outboxe events for rækker `UPDATE`'en ikke rører og udløse rowcount-guarden. `_get_summary`
filtrerer også nu, så det rapporterede total matcher det API'et viser.

**3. `rowcount` kunne ikke bruges.** `delete` blev skrevet som goal-services `update(...)` +
`result.rowcount == 1`, men `rowcount` er utypet på `Result` og mypy-gaten afviste det (goal er
uden for gaten, derfor findes mønstret dér). Landede på `.returning(TransactionModel.id)`, som
er typet og siger det stærkere: vi ramte *den* række, ikke bare én række.

**4. Downgrade kan fejle, ikke bare genoplive data.** Planens rollback-afsnit nævnte at rækker
bliver synlige igen. Det udeladte: hvis en tombstone er blevet re-importeret under samme
`(account_id, external_id)`, kan det brede index ikke genskabes, og `downgrade` fejler. Det er
det ærlige signal, og det står nu i migrationens docstring.

### Kontroller kørt

Vanen fra P2-31/P3-23 holdt: hver gang noget skulle bevises, blev også det modsatte målt.

- Prædikaterne fjernet fra repositoriet → 7 af de 9 soft-delete-integrationstests fejler.
  De to der ikke gør, afhænger ikke af læse-stien.
- Consumer-grenen fjernet → 1 af 4 fejler (fundet ovenfor).
- Migrationstesten har både `test_reimport_after_soft_delete_is_allowed` og
  `test_two_live_rows_still_rejected` — indexet må ikke være holdt op med at håndhæve.
- DLQ-reproduktionen kørt med kontrol: slettet tx → DLQ 2 → 2; id der aldrig har eksisteret →
  DLQ 2 → 3 med backoff i loggen. Uden kontrollen havde vi kun vist at grenen var *lukket*,
  ikke at den var *delt*.

### Efterladt bevidst

- DLQ'en holder nu 3 beskeder: 2 fra det oprindelige fund (ikke purget — det er evidens) plus
  1 fra kontrol-kørslen ovenfor. Den sidste er et testartefakt og kan fjernes med
  `rabbitmqctl purge_queue`, men det tager de to originale med sig.
- Tombstones har ingen retention. Bevidst non-goal; hvad der skal ske med dem er ikke dette
  items beslutning.
