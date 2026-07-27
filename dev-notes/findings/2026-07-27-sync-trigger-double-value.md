---
title: Alle bank-syncs fejlede i to dage på en dobbelt .value — som intet i repoet kunne fange
date: 2026-07-27
severity: HIGH
area: banking, cross
status: resolved
resolved-by: commit 34e68040 (fix + regressionstest); rodårsagen → P2-31, P3-41
---

# Dobbelt `.value` på sync-claimet — og hvorfor tre lag tavshed slap den igennem

**Symptom (som brugeren så det)**: manuel bank-sync på user 1 fejlede i browseren med

```
Access to fetch at 'http://localhost:8009/api/v1/bank/connections/<id>/sync'
blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

**Det var ikke CORS.** `banking-service` kastede en exception før CORS-middlewaren nåede at
sætte sine headers, så en 500 nåede browseren forklædt som en oprindelsesfejl. Repoets
eksisterende regel ("CORS-fejl er ofte server-crashes der maskerer sig — tjek `docker logs`
først") holdt og sparede diagnosetid; den er nu bekræftet anden gang.

**Den faktiske fejl**, `postgres_bank_connection_repository.py:136`:

```
AttributeError: 'str' object has no attribute 'value'
    .values(..., sync_trigger=trigger.value)
```

`b16d402f` (2026-07-25, "type sync-claimets trigger som SyncTrigger") ændrede porten og
adapteren til at tage `SyncTrigger` og pakke den ud med `.value` — men rørte ikke
`service.py`, den eneste kalder, som allerede sendte `trigger.value`. Tre kaldsteder
(`service.py:274`, `:294`, `:310`), altså **hver eneste bank-sync, manuel som natlig, i to
dage**. Porten-docstringen skrev endda "both callers already pass `SyncTrigger` members" —
en påstand om kalderne, formuleret uden at læse dem.

## Hvorfor det var usynligt i to dage

Tre uafhængige lag tavshed, og det er dem der er værd at huske frem for selve typefejlen:

1. **Testene kunne ikke fange det.** `uow.connections` var en bar `AsyncMock()`, som tager
   imod hvad som helst. Ni tests kalder `try_claim_sync`; alle ni sendte en `str` mod en port
   der erklærer `SyncTrigger`; alle ni var grønne. Målt: med fixet fjernet igen giver suiten
   **2 failed, 22 passed** — de 22 er beviset for at den eksisterende dækning var blind.
2. **Ingen statisk typecheck kører nogen steder.** CLAUDE.md foreskriver "mypy for type
   checking (zero errors policy)". Virkeligheden: 0 af 13 services kalder mypy i Makefile
   eller CI, kun `analytics-service` har overhovedet en config, og roden har en
   `pyrightconfig.json` som intet invokerer og hvis `extraPaths` dækker 2 services. En
   annotation er dokumentation her, ikke en begrænsning. → **P2-31**
3. **Et forældet image skjulte det.** `banking-service`-containeren kørte kode fra før
   `b16d402f`, så bugget var i master uden at være i drift. Det blev synligt i det sekund
   P3-40's `--force-recreate` satte alle containere på master-koden.

Punkt 3 er P3-40's spejlbillede og værd at sige rent: **staleness havde beskyttet
produktionen mod en fejl i master.** Det er ikke et argument for staleness — det er et
argument for at man ikke ved hvad man kører før man ved hvad man kører.

## Blast radius

Den natlige sync-scheduler (F1-05) ramte samme kodesti, så den har også fejlet siden
2026-07-25. Ingen datatab: claimet skrives før fetch, så fejlen sker *før* der hentes noget,
og transaktions-importen er dedup'et uanset. Efter fixet: 16 transaktioner importeret
16:11:52, `last_synced_at` sat 16:11:54, claim-felterne ryddet — hele ADR-0003-kæden kørte.

## Fix

`34e68040`: de tre kaldsteder sender enummet; `uow.connections` er spec'd mod
`IBankConnectionRepository`; ny regressionstest asserter på argumentets **type**,
parametriseret over hele `SyncTrigger`.

Bemærk hvad `spec=` **ikke** køber: den begrænser attribut-navne, ikke argumenttyper, så den
ville ikke selv have fanget denne fejl. Det er derfor testen asserter på typen eksplicit. Den
generelle version af begge dele hører hjemme i P2-31, ikke i en per-fil-vane. → **P3-41**

## Relateret

- [per-worker image staleness](2026-07-25-per-worker-image-staleness.md) / P3-40 — hvorfor
  det dukkede op i dag og ikke i mandags.
- CLAUDE.md's regel om CORS-fejl som maskerede server-crashes: holdt.
