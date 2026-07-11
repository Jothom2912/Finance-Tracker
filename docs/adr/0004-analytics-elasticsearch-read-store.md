# ADR-0004: Analytics-service med Elasticsearch som central read store

Dato: 2026-07-11
Status: Accepteret (cutover udført samme dag)

## Kontekst

Gatewayens "analytics read-side" var en illusion: `HttpAnalyticsReadRepository`
hentede alle transaktioner via HTTP fra transaction-service per request, og
`AnalyticsService` aggregerede i Python. Det gav (1) O(n) netværk+CPU per
dashboard-visning, (2) ingen mulighed for fuldtekstsøgning eller lange
tidsserier, og (3) divergerende aggregeringsregler mellem gateway og
budget-service ("forbrug vs. budget"-mismatchet: forskellig datakilde,
expense-klassifikation og periodegrænser).

## Beslutning

**analytics-service ejer Elasticsearch** som denormaliseret CQRS read store
og eksponerer aggregerings-/søge-endpoints (`/api/v1/analytics/*`, JWT).
Gatewayen læser præ-aggregerede svar via den grove port
`IFinancialAnalyticsPort`; GraphQL-skemaet er uændret for frontenden.
Database-per-service bevares: kun analytics-service rører ES.

```
Frontend ──GraphQL──▶ gateway-service ──HTTP──▶ analytics-service ──▶ Elasticsearch
                                                     ▲
                                        RabbitMQ (transaction.* account.*
                                        category.*/subcategory.* goal.*)
```

## Index-/alias-konvention

- Fysisk index `<navn>_v1` bag alias `<navn>` (`transactions`, `accounts`,
  `taxonomy`, `goals`). Alle læs/skriv går via alias; reindex = opret v2,
  swap alias. Bootstrap er idempotent og sker ved opstart af både API og
  consumer (`ensure_indices`).
- `dynamic: strict` — kontrakt-drift fejler højlydt.
- Beløb som `scaled_float(100)`: øre-præcis heltalsmatematik i aggs.
  Events serialiserer beløb som decimal-strenge; stores parser med `Decimal`.
- `description` indekseres med den indbyggede **danish analyzer** (stemming:
  "forsikringen" matcher "forsikring") + `.raw` keyword-subfield til
  merchant-aggregeringer.
- Tenant-isolation er kontraktuel: alle queries filtrerer `user_id` (fra JWT)
  og `account_id`.

## Kanoniske aggregeringsregler

Ejes af `services/analytics-service/app/domain/`:

- **Expense/income-klassifikation** (`classification.py`):
  `transaction_type` er primært signal; fortegns-fallback KUN for tomme
  typer (`is_expense = type=="expense" or (type=="" and amount<0)`).
- **Budgetmåneder** (`budget_period.py`): transaktioner på/efter kontoens
  `budget_start_day` hører til NÆSTE måned. I ES udtrykt som
  `date_histogram(calendar_interval=month, offset=+(start_day-1)d)`;
  bucket-labels via `histogram_bucket_to_budget_month` (property-testet
  mod `determine_budget_month`).
- **Kanonisk transaktionsorden**: `tx_date desc, transaction_id desc`.
- Buckets nøgles på id'er (aldrig navne); labels har fallbacks
  "Ukategoriseret"/"(Ingen underkategori)".

**Kendt, dokumenteret divergens**: budget-service tæller kun
`transaction_type=="expense"` (ingen fortegns-fallback) i rå kalendervinduer
via live HTTP til transaction-service. `budget_summary` forbliver en proxy
(der findes ingen budget-definition-events). Follow-up: budget-service bør
adoptere de kanoniske regler ovenfor — indtil da kan forbrugs-tal afvige
mellem budget-widget og overview for konti med legacy-rækker uden type.

## Idempotens uden processed_events-tabel

Consumers er idempotente via **dokument-`_id` = entity-id + event-timestamp-
guards** i painless scripted upserts — ikke en DB-backed inbox:

- Transaktionsdokumenter har TO guards: `core_event_ts` (created/updated)
  og `categorization_event_ts` (categorized). De to event-strømme kan
  ankomme i vilkårlig orden uden at clobre hinanden; categorized-før-created
  giver et partielt dokument, der er usynligt for queries (mangler
  account_id/user_id) indtil core-eventet kompletterer det.
- `is_deleted` er terminal — sene replays genopliver aldrig.
- Fuld-state events (accounts/goals/taxonomy) bruger én `event_ts`-guard.
- Kategori-/subkategori-renames propageres til denormaliserede navne via
  `update_by_query` (conflicts=proceed), men kun når taxonomy-upserten
  faktisk blev anvendt — stale events ruller aldrig navne tilbage.

**Trade-off accepteret**: intet audit-trail over konsumerede events (mod
CLAUDE.md's processed_events-mønster). Projektioner er konvergente og fuldt
genopbyggelige via backfill; Postgres i analytics-service alene til en
inbox ville modsige dens rolle som genopbyggelig read model.

## Backfill

`python -m app.tools.backfill --user-id N` skriver gennem samme projection
stores med `event_ts=0`, så ethvert live event vinder — kan køre sideløbende
med live consumption og genkøres frit. Taksonomien seedes først; navne
opløses derfra (ADR-003) med rækkens denormaliserede navn som fallback.
NB: transaction-services `find_by_account` ignorerer skip/limit (returnerer
alt per side); backfillen stopper derfor på første side uden nye id'er.

## Dual-read verifikation og cutover

`ANALYTICS_READ_SOURCE ∈ {legacy, dual, analytics}` i gatewayen:

1. **dual**: server legacy, skygge-læs analytics, log divergenser som
   strukturerede warnings med felt-sti-diffs (float-tolerance ±0.01 pga.
   float64 vs scaled_float; eksakthed dækket af golden-integrationstests
   der seeder ES med gatewayens test-datasæt og asserter gatewayens tal).
2. Kør backfill, brug dashboardet, grep `analytics.dual_read.divergence`.
3. **Cutover-kriterium**: nul divergenser på overview/expenses-by-month.
   Verificeret 2026-07-11 (konto 1 med start_day=26 og konto 2 med
   start_day=1): eneste divergens var den forventede ordens-klasse på
   limit-trunkerede transaktionslister (legacy = ankomstorden).
4. Flip til `analytics`. Rollback = flip tilbage.

Live event-stien er e2e-verificeret: POST transaktion → outbox → RabbitMQ →
consumer → ES-dokument (<6 s); DELETE → tombstone.

## Oprydning efter én stabil release

- Slet `LegacyFinancialAnalyticsAdapter`, `DualReadFinancialAnalyticsRepository`,
  `HttpAnalyticsReadRepository` og gatewayens `AnalyticsService`-aggregering
  (+ REST-endpoints `/dashboard/*` der stadig bruger legacy-stien direkte).
- Fjern derefter `ANALYTICS_READ_SOURCE`-flaget.

## Prod-hærdning (udestående)

Dev kører single-node ES uden xpack security (kun genopbyggelige
projektioner; tab er acceptabelt). Prod skal aktivere xpack auth + TLS og
snapshots, og bør overveje replicas>0.
