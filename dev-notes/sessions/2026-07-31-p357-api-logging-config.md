---
date: 2026-07-31
topic: P3-57 + P3-58 — logging-konfiguration i alle 12 API-processer, og de to fund målingen afdækkede
---

# Session 2026-07-31 — P3-57: logging-konfiguration i de 12 API-processer

## Done

Fire commits, én per fase, plus docs:

| commit | indhold |
|---|---|
| `772a891d` | `disable_existing_loggers=False` i de 8 sidste `env.py` (P3-58) |
| `4d2db80c` | ny pakke `shared/observability` med `setup_logging()`, 8 tests |
| `31c15ca6` | `messaging.setup_worker_logging` delegerer til den; 23 kaldsteder urørte |
| `3cf32022` | `setup_logging()` i alle 12 `app/main.py` + dep/COPY/lock per service |

Docs: [plan + Outcome](../plans/2026-07-31-p357-api-logging-config.md#outcome),
[finding](../findings/2026-07-31-account-service-log-silenced-by-alembic.md), BACKLOG (P3-57 og
P3-58 done, **P3-59** ny), STATUS, 00-INDEX, CLAUDE.md.

Verificeret i den kørende stak (52 containere), ikke kun statisk: access-linje med niveau +
tidsstempel + logger-navn i **12 af 12**; app-niveau `WARNING` 0 → 1 med fuldt format i fire
services; app-niveau `INFO`, som var dødt overalt, når loggen i to; `uvicorn.error` stadig
levende som negativ kontrol; workernes format uændret; 24 e2e grønne; `make check` + tests
grønne i alle 11 uv-services.

## Learned / surprised

**1. Fælden planen ville vogte imod var allerede i drift.** Jeg gik efter baseline-tal og
fandt at `account-service` havde **4 logliner på 35 timers uptime** — ingen access-log — mens
den var `healthy` med `restarts=0` og svarede `/health` på 10 ms. `alembic/env.py`s
`fileConfig()` defaulter `disable_existing_loggers=True`, og `account` er den eneste service
der migrerer *i API-processen*. Skaden er snittet mellem to egenskaber, hvor ingen af dem er
forkert alene. Egen finding + P3-58.

**2. `disable_existing_loggers=False` var nødvendigt men ikke tilstrækkeligt — og det er den
mest genbrugelige lektie herfra.** Efter det fix kom access-logs tilbage i account-service,
men uden tidsstempel, og `logger.info` var stadig dødt. Fordi `fileConfig` ikke kun *slukker*
loggere: den **erstatter** root-handleren med `alembic.ini`s og sætter root til `WARN`. Enhver
`fileConfig`/`dictConfig` senere i samme proces er en **fuld rekonfiguration, ikke et delta**.
Spørgsmålet er aldrig "slukker den noget", men "hvem konfigurerede sidst".

Det der afslørede omfanget var **en linje der manglede**, ikke en linje der var forkert:
`Database migrations applied successfully` var helt væk. Havde jeg kun tjekket formatet,
havde jeg kaldt det kosmetik og ladet det ligge.

**3. Efter-målinger kan også være tilfældigt rigtige.** En probe der sendte ugyldig HTTP til
alle 12 porte gav 12 × `grep -c WARNING` 0 → 1, og det var lige ved at blive hovedresultatet:
et adfærdsmæssigt før/efter der dækkede alle 12, inklusive de fem uden app-logning. Kontrollen
viste at uvicorns *eget* format altid har været `WARNING:  <besked>` og dermed matchede
`grep WARNING` også før. Det ægte før/efter findes kun på app-niveau. Sidestykke til
`feedback_baseline_can_be_accidentally_right`, med fortegnet vendt — her var det efter-tallet
der var flatterende, ikke baselinen der var uskyldig.

**4. Færdig-kriteriet var ikke opnåeligt, og det kunne ikke vides uden at måle.** Planen
sagde "trig en kendt warning i hver af de 12". Fem services har ingen; `goal-service` har nul
logging-statements i hele API-processen. Det blev **P3-59** frem for scope-creep, og det
tvang et bedre universelt kriterium frem (access-linjens format), som samtidig gjorde
beslutningen om at overtage uvicorns loggere **bærende frem for kosmetisk**.

**5. Den eksisterende kontrol var gratis og afgjorde designet.** `gateway-service` havde
allerede en fungerende `basicConfig` på modul-niveau. At den virkede beviste at uvicorn
konfigurerer logging i `Config.__init__`, altså *før* app-importen — så et import-tids-kald
vinder, og de `--log-config`-filer i 11 Dockerfiles som planen ellers ville have krævet var
unødvendige. Kontrollen sparede mere arbejde end den kostede at finde.

**6. Bivirkning der er en gevinst:** `saga-service` logger intet selv, men får nu en
grep-bar, tidsstemplet `WARNING  [uvicorn.error] Invalid HTTP request received.` — selv de
fem tavse services har et minimum af observerbarhed de ikke havde før.

## Open ends

- **P3-59** er den direkte fortsættelse: hvilke afvisninger og domænefejl i `account`, `user`,
  `goal`, `notification` og `saga` burde efterlade et spor, og på hvilket niveau. Ikke et fix
  men et review.
- **P3-17** har fået et konkret argument: `_reassert_logging()` i account-service er et
  plaster der forsvinder, når migrations flyttes ud af API-processen.
- **Ikke verificeret, og står som det:** `gateway`s `auth.py:113` fyrede ikke (proben-brugeren
  *har* en `Default Account`, fordi registrering opretter én via sagaen — betingelsen kræver
  en bruger med nul konti), og `ai`s `pipeline.py:109` kræver at Ollama-routingen lykkes
  først, hvilket P3-46 gør upålideligt under fuld stak.
- **Migration af de 23 `setup_worker_logging`-kaldsteder** til `observability` direkte er
  bevidst ikke gjort; shimmen holder dem. Eget S-item hvis det nogensinde er værd at rydde.
- **`account-service` kan stadig ikke køre `make test` lokalt** (`pytest: command not found`,
  P3-39). Prøvet, ikke antaget.

## Notes updated

- **Nyt:** `plans/2026-07-31-p357-api-logging-config.md`,
  `findings/2026-07-31-account-service-log-silenced-by-alembic.md`, denne session-log
- **Opdateret:** `backlog/BACKLOG.md` (P3-57 + P3-58 done, P3-59 tilføjet), `STATUS.md`,
  `00-INDEX.md`, `CLAUDE.md` (logging-konventionen)
