---
date: 2026-07-28
title: P2-25 transaction soft-delete — dedup ekskluderer tombstones, saga-rollback bliver soft, consumeren acker
status: accepted
---

# P2-25: soft-delete på `transactions`

**Context.** `transactions` var hard-deletet (`postgres_transaction_repository.delete` →
`session.delete(model)`), mod CLAUDE.md's egen anti-pattern-liste — goal-service fik
soft-delete i P3-16, den mest audit-relevante entitet i systemet fik det ikke. Det bed i
kombination med `categorized_consumer`, som konflaterede to tilstande: en `transaction.categorized`
for en række der ikke fandtes kunne lige så godt være "ikke committet endnu" (retry er rigtigt)
som "slettet for altid" (retry er meningsløst). tx 1133 blev oprettet, kategoriseret og slettet
mid-flight → 5 retries med 1/2/4/8/16 s backoff på en `prefetch=1`-consumer → DLQ.
Se [finding](../findings/2026-07-25-transaction-hard-delete-categorized-dlq.md).

Rækkefølgen var bundet: migrationen alene har ingen værdi, og consumer-grenen alene er
umulig at skrive. P3-37 er derfor udmøntningen af P2-25, ikke et selvstændigt item.

## Decisions

1. **Dedup ekskluderer slettede rækker.** Både `find_existing_dedup_keys` og
   `find_existing_external_ids` får `deleted_at IS NULL`, og den partielle unique-index
   `uq_transactions_account_external_id` udvides med `AND deleted_at IS NULL` (migration 013).
   De to *skal* være enige: filtrerer queryen ikke, men indexet gør, bliver re-import stille
   sprunget over; filtrerer indexet ikke, men queryen gør, rammer re-import en
   unique-violation der læser som en saga-fejl.
   *Trade-off:* re-import giver et nyt id, og det gamle bliver liggende som tombstone. Til
   gengæld er dagens observerbare adfærd bevaret eksakt — soft-delete er usynlig for alt
   andet end auditsporet. Alternativet ("slettet = set og fravalgt") gør delete til et
   permanent, usynligt importfilter brugeren ikke kan fortryde, og bryder rollback→re-import.
   **Genoplivning (clear `deleted_at`) er afvist**, fordi ES-guarden er terminal: alle tre
   update-scripts noop'er på `is_deleted == true`, så read-modellen ville aldrig få rækken
   tilbage. Vi ville skulle rive den envejs-garanti ned først.

2. **Saga-kompensationen `rollback_import` bliver soft.** Den går gennem samme use case
   (`saga_command_consumer` → `service.delete_transaction`) og får ingen særvej.
   *Trade-off:* rækker der aldrig burde have eksisteret akkumuleres. Accepteret, fordi to
   slette-semantikker er dyrere at holde styr på end nogle tombstones, og fordi auditsporet
   på en *fejlet* import faktisk er værd at have. Re-import efter rollback virker i kraft af
   beslutning 1.

3. **Consumeren acker — den DLQ'er ikke.** Finding'ens eget forslag var `PoisonMessageError`.
   Det er forkert: `PoisonMessageError` sender til DLQ, og en kategorisering for en slettet
   transaktion er et *forventet* race, ikke en fejl der kræver menneskelig opmærksomhed. At
   DLQ'e den ville bevare præcis det problem finding'en beskriver — "en DLQ der samler
   godartede beskeder holder op med at være et signal". Grenen returnerer stille, som
   duplikat-grenen gør, med én INFO-linje der navngiver transaktionen.
   *Restrisiko:* hvis `deleted_at` en dag sættes bredt (fx et fejlagtigt script), acker
   consumeren nu stille i stedet for at larme. INFO-linjen er det eneste spor — derfor bærer
   den transaction-id'et og ikke en generisk "skipped".

4. **`_get_transaction` i consumeren får bevidst *ikke* filteret.** Alle andre læse-stier
   har det. Denne skal kunne se tombstonen, ellers kollapser de to tilstande tilbage til én
   og DLQ-buggen er genindført. Det står i metodens docstring, ikke kun her.

5. **Cleanup-scriptet soft-deleter også, og ignorerer tombstones i dubletsøgningen.**
   `scripts/cleanup_pg_duplicates.py` ville ellers være den eneste tilbageværende hard delete
   — repoets eget værktøj der bryder invarianten. Filteret i `_find_duplicates` er ikke
   kosmetik: en tombstone og dens legitime re-import ville danne en "gruppe", og da tombstonen
   har det laveste id ville den blive *beholdt* og den levende række slettet.

## Hvad der viste sig at være forkert i planen

Planen tilskrev DLQ-fixet til consumer-grenen. **Kontrollen siger noget andet.** Med grenen
fjernet, men soft-delete på plads, fejler kun én af klassens fire tests: rækken *findes* nu, så
`_get_transaction` returnerer den, og der backes aldrig off. Soft-delete alene lukker altså
DLQ-stien. Grenens egen værdi er at en tombstone ikke får sine kategoriseringsfelter overskrevet,
plus sporet i loggen. Det står i testklassens docstring, så den ikke bliver læst som bevis for
noget den ikke viser.

## Non-goals

- **Ingen kontrakt-ændring.** `TransactionDeletedEvent` beholder sit felt-sæt og
  `event_version = 1`. Consumere ser ingen forskel.
- **Ingen ændring i analytics eller ES** — hverken mapping, projektion eller filtre.
  `transaction.deleted` blev allerede konsumeret og satte `is_deleted: true`; `_base_filters`
  havde allerede `{"term": {"is_deleted": False}}`.
- **Intet restore/undelete-endpoint** og ingen purge/retention-jobs. Hvad der skal ske med
  tombstones på sigt er ikke dette items beslutning.
- **`planned_transactions` røres ikke** — den har sin egen `is_active`-deaktivering.

## Verifikation

Statisk: `make -C services/transaction-service test / lint / typecheck` grønne (195 unit +
69 integration), `make test-e2e` 24 passed.

Kørende stak (compose, alle services): `deleted_at`-kolonnen og det narrowede index verificeret
i `\d transactions`, ikke kun at `alembic upgrade head` exit-kodede 0. Oprettet → slettet:
`GET` giver 404, rækken forsvinder fra listen, `total_count` falder med præcis 1, rækken ligger
i Postgres med `deleted_at` sat, anden DELETE giver 404. ES-dokumentet er `is_deleted: true`, og
`/analytics/overview` falder med præcis rækkens beløb (500,00 → 0,00). Re-import af samme nøgle
giver et nyt id, og begge rækker findes i Postgres.

**DLQ-reproduktionen kørt med sin kontrol.** Treatment: en `transaction.categorized` for den
slettede transaktion → DLQ'en vokser ikke, én INFO-linje
(`Transaction 1400 deleted — categorization moot, acking`), ingen backoff. Kontrol: samme publish
med et id der aldrig har eksisteret → backer stadig off og lander i DLQ'en (dybde 2 → 3). Uden
kontrollen havde vi kun vist at grenen var *lukket*, ikke at den var *delt*.

Kontroller kørt også på testniveau: med prædikaterne fjernet fejler 7 af de 9
soft-delete-integrationstests; de to der ikke gør, afhænger ikke af læse-stien.

## Rollback

`alembic downgrade -1` + `git revert` af prædikat-commit'en. To ting skal siges højt:
en downgrade **genopliver data** (rækker slettet i mellemtiden bliver synlige igen — den rigtige
retning for et fejlgreb, men ikke en no-op), og den **kan fejle**: hvis en tombstone er blevet
re-importeret under samme `(account_id, external_id)`, kan det brede index ikke genskabes.
Det er det ærlige signal — ryd dubletterne manuelt frem for at udvide indexet tilbage i stilhed.
