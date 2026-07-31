---
title: account-service' API-proces er helt tavs — alembics fileConfig slukker uvicorns loggere
date: 2026-07-31
severity: medium
area: [account, observability, cross]
status: resolved
resolved-by: P3-58, 2026-07-31 (772a891d + 3cf32022) — disable_existing_loggers=False i alle 9 env.py + _reassert_logging() efter migrationen; kwarg alene var ikke nok, se Fix. Verificeret live med mutation.
backlog-items: [P3-57, P3-17]
related:
  - ../plans/2026-07-31-p357-api-logging-config.md
---

# account-service' API-proces er helt tavs — alembics `fileConfig` slukker uvicorns loggere

Fundet 2026-07-31 under P3-57's før-måling, ikke ledt efter.

## Symptomet

`account-service` har **fire logliner i alt efter 35 timers uptime**, og rapporterer samtidig
`healthy` med `restarts=0`:

```
account-service-1  | INFO:     Started server process [1]
account-service-1  | INFO:     Waiting for application startup.
account-service-1  | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
account-service-1  | INFO  [alembic.runtime.migration] Will assume transactional DDL.
```

Læg mærke til hvad der **mangler**: `Application startup complete`, og hver enkelt
access-log-linje. De øvrige 11 API-services har ~630 linjer hver i samme vindue, fordi
compose-healthchecken poller `/health` hvert 10. sekund.

Servicen er ikke syg. Den svarer:

```
$ curl -s -o /dev/null -w "health=%{http_code} tid=%{time_total}s\n" http://localhost:8004/health
health=200 tid=0.009976s
$ docker inspect … --format '{{.State.StartedAt}} restarts={{.RestartCount}} health={{…}}'
2026-07-29T12:24:27Z restarts=0 health=healthy
```

Healthchecken kører — den er grunden til at containeren er `healthy` — men **dens 12.000+
requests har ikke efterladt en eneste linje.**

## Mekanismen

`alembic/env.py:20` kalder `fileConfig(config.config_file_name)`.
`logging.config.fileConfig` defaulter `disable_existing_loggers` til **`True`**, så den slukker
hver logger der ikke er nævnt i `alembic.ini` — inklusive uvicorns tre.

Målt inde i den kørende container, med præcis det kald `env.py` laver:

```
FØR fileConfig:  uvicorn.access disabled=False handlers=1 | uvicorn.error disabled=False
EFTER fileConfig: uvicorn.access disabled=True  handlers=1 | uvicorn.error disabled=True
```

Handleren sidder stadig på loggeren — `handlers=1` både før og efter. Det er `disabled`-flaget
der dropper records, og det er derfor symptomet ikke ser ud som en manglende konfiguration.

**Det afgørende er *hvor* kaldet sker.** `account-service` er den **eneste** af de 12 services
der kører migrations **inde i API-processen**: `app/main.py:33` kalder `_run_migrations()` fra
`lifespan`, som importerer og kører alembic i den proces der skal betjene requests. De øvrige
8 alembic-services gør det i CMD (`alembic upgrade head && exec uvicorn …`), altså i en
**tidligere proces**, hvor `fileConfig`'s bivirkning dør sammen med processen.

To grep-verificerede tal, som tilsammen er hele forklaringen:

| | services |
|---|---|
| `env.py` kalder `fileConfig` | **9 af 9** med migrations |
| … med `disable_existing_loggers=False` | **1** — `transaction-service/migrations/env.py:25` |
| kører migrations i API-processen | **1** — `account-service/app/main.py:33` |

Skaden er snittet mellem de to sidste rækker, og det snit er i dag præcis
`account-service`. **`transaction-service` er værd at bemærke: den har allerede
`disable_existing_loggers=False`.** Nogen er altså løbet ind i denne fælde én gang og har
lukket den ét sted, uden at det blev en konvention — så de resterende 8 står som de gjorde.

## Hvorfor det er værre end en tavs service

1. **Det er P3-57's fælde, i drift.** P3-57's plan navngav `disable_existing_loggers` som den
   stille fælde vores *egen* nye `dictConfig` skulle vogte imod. Fælden var ikke hypotetisk —
   den har været aktiv i repoet hele tiden, i en service ingen har set på.
2. **Vores fix ville blive rullet tilbage af alembic i netop denne service.** P3-57 kalder
   `setup_logging()` på modul-niveau i `app/main.py`, altså ved import. I `account-service`
   kører `fileConfig` **bagefter**, i `lifespan`. Uden en ændring i `env.py` ville
   `account-service` derfor være den ene service hvor P3-57 leverer koden og ikke virker — og
   den ville se fikset ud i enhver statisk kontrol.
3. **Det er en latent landmine for [P3-17](../backlog/BACKLOG.md#p3-17).** P3-17 vil flytte
   migrations ud af API-containeren som et eksplicit trin. Går den anden vej for nogen — en
   service der begynder at kalde migrations in-process, eller en worker der importerer
   `env.py` — så dør logningen i den proces, tavst.
4. **Instrumentet var blindt for det.** `restarts=0`, `healthy`, `health=200`. Alle tre
   kontroller siger "fin". Den ene ting der ville have vist det — er der access-logs? — er
   ikke noget nogen gate læser.

## Fix — landet 2026-07-31 (P3-58, commits `772a891d` + `3cf32022`)

**Vigtig tilføjelse fra implementeringen: `disable_existing_loggers=False` var nødvendigt
men ikke tilstrækkeligt.** `fileConfig` **erstatter** også root-handleren med
`alembic.ini`'s (intet tidsstempel) og sætter root til `WARN` — så `account-service` fik
sine access-logs tilbage, men mistede stadig `app.*`-logning efter migrationen. Målt:
`Database migrations applied successfully` udgik helt af loggen. Der skulle et
`_reassert_logging()` til efter migrationen. Enhver `fileConfig`/`dictConfig` i samme
proces er en **fuld rekonfiguration, ikke et delta** — spørgsmålet er ikke "slukker den
noget", men "hvem konfigurerede sidst".

Hvad der landede:

- `disable_existing_loggers=False` i alle **9** `env.py`, ikke kun `account-service`'s.
  `transaction-service` var præcedensen. De 8 andre er harmløse i dag, men det er en egenskab
  ved deres *procesopdeling*, ikke ved deres kode — og P3-17 er ved at ændre procesopdelingen.
- `_reassert_logging()` i `account-service/app/main.py` efter migrationen, i begge grene.
  Plaster med item-reference: **P3-17 fjerner behovet** ved at tage migrations ud af
  API-processen, og det er den rigtige løsning.

Verificeret i den kørende stak, ikke statisk — og med mutation, fordi en genstartet container
ellers selv kunne forklare de nye linjer:

| | access-linjer | `Application startup complete` |
|---|---|---|
| før (35 timers uptime) | 0 | 0 |
| efter | 2 | 1 |
| kwarg rullet tilbage (~32 s polling) | 0 | 0 |
| gendannet | 2 | 1 |

Slutresultatet, hvor `[app.main]`-linjen er den der forsvandt undervejs:

```
2026-07-31 00:05:54,222 INFO     [app.main] Database migrations applied successfully
2026-07-31 00:05:54,222 INFO     [uvicorn.error] Application startup complete.
2026-07-31 00:05:58,765 INFO     [uvicorn.access] 127.0.0.1:36594 - "GET /health HTTP/1.1" 200
```

De to `alembic.runtime.migration`-linjer beholder med vilje alembics eget format: det er
alembics konfiguration for alembics output.
