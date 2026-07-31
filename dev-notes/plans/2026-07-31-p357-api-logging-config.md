---
title: P3-57 — logging-konfiguration i de 12 API-processer (shared/observability)
date: 2026-07-31
status: done
backlog-items: [P3-57, P3-58]
commits: [772a891d, 4d2db80c, 31c15ca6, 3cf32022]
related:
  - ../findings/2026-07-31-account-service-log-silenced-by-alembic.md
  - ../findings/2026-07-27-sync-trigger-double-value.md
  - 2026-07-29-f208-user-profile-write-path.md
  - 2026-07-29-p242b-dependency-readiness.md
---

# P3-57 — logging-konfiguration i de 12 API-processer (shared/observability)

## Goal

Efter denne plan har **alle 12 API-processer** en eksplicit logging-konfiguration, så
`logger.info` fra `app.*` når containerens log, og hver linje — også uvicorns egne — bærer
**niveau, tidsstempel og logger-navn** i ét format.

**Færdig-kriteriet er omskrevet efter step 1's måling, og det er planens vigtigste rettelse.**
Det oprindelige kriterium — "en kendt warning findes med `docker compose logs <svc> | grep
WARNING`, tom før, ikke-tom efter" — er **ikke opnåeligt i 5 af de 12 services, fordi de ikke
har nogen warning at affyre.** Se [Step 1's resultat](#step-1s-resultat-målt-2026-07-31).
Kriteriet er derfor delt i to, og pointen er at det ene gælder alle 12:

- **Alle 12, adfærdsmæssigt:** uvicorns **access-log-linjer** bærer niveau, tidsstempel og
  logger-navn. Det virker som universelt kriterium fordi compose-healthchecken poller
  `/health` hvert 10. sekund, så hver service producerer access-linjer af sig selv — ingen
  trigger skal opfindes. **Det gør beslutning (b) bærende frem for kosmetisk:** havde vi
  ladet uvicorn beholde sit eget format, ville der ikke findes et adfærdsmæssigt kriterium
  der dækker alle 12.
- **De 6 der har en reachable warning, adfærdsmæssigt:** `grep -c WARNING` går fra 0 til ≥1
  på samme trigger.
- **Alle 12, mekanisk:** in-container-proben viser `root_handlers=1` og
  `info_enabled=True`.

Uden før/efter-par er planen ikke bevist, kun leveret. Før-tallene står nedenfor og er målt
inden nogen kode blev rørt.

## Context

P3-57, målt 2026-07-29 under F2-08. uvicorn konfigurerer kun sine tre egne loggere
(`uvicorn`, `uvicorn.access`, `uvicorn.error`). Root-loggeren står med nul handlers og
default-niveau `WARNING`, så alt under `app.*` arver `WARNING`: `logger.info` dør på
niveau-tjekket, og `logger.warning` slipper igennem til Pythons `logging.lastResort` — en
handler uden formatter, der skriver den bare besked til stderr.

**Konsekvensen er værre end tavshed, og det er grunden til at itemet er M og ikke S:
`grep WARNING` returnerer intet, også når warnings faktisk er affyret.** Det er en blind
instrument-fælde af samme klasse som P3-54's exit-0-predikat og `/ready`-endpointet der kun
CI læste. Repoet har nu så mange af dem at klassen har sit eget mønster, og hver fremtidig
live-verifikation betaler for denne.

**Målt 2026-07-31 i den kørende stak, uafhængigt af F2-08's måling** — samme `dictConfig`
reproduceret inde i tre byggede images:

| service | root handlers efter uvicorns dictConfig | effektivt niveau for `app.*` |
|---|---|---|
| gateway-service | `[StreamHandler <stderr>]` | **INFO** |
| user-service | `[]` | WARNING |
| analytics-service | `[]` | WARNING |

**Gateway er den 12. service, og den er planens vigtigste fund: den er en eksisterende,
fungerende kontrol.** `gateway-service/app/main.py:11` kalder `logging.basicConfig` på
modul-niveau, og det *overlever* uvicorns `dictConfig`, fordi uvicorn konfigurerer logging i
`Config.__init__` — altså **før** app-importen. Det afgør en implementeringsdetalje uden at
vi skal gætte: fixet behøver **ikke** `--log-config`-filer i 11 Dockerfiles (som skulle
COPY'es ind i images og holdes i sync med hinanden). Et kald i hver `app/main.py` er nok, og
gateway beviser at det virker i netop dette repo, under netop disse images.

To ting fundet undervejs, som planen skal forholde sig til frem for at efterlade:

1. **`LOG_LEVEL` er dead config i 6 af 7 services der erklærer den.** `account`, `gateway`,
   `categorization`, `transaction`, `budget`, `user` og `banking` har den i `config.py`; kun
   gateway læser den. `ai`, `analytics`, `goal`, `notification`, `saga` har den slet ikke.
   Samme klasse som P3-42's ubrugte Redis-cache-backend.
2. **Der findes allerede to uenige formater.** gateway bruger
   `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`;
   `shared/messaging/messaging/logging.py` (workernes `setup_worker_logging`, 23 kaldsteder i
   10 services) bruger `"%(asctime)s %(levelname)-8s [%(name)s] %(message)s"`. Derudover
   kalder analytics' fire worker/tool-moduler `logging.basicConfig` direkte — et tredje
   mønster. Ét format skal vinde, ellers er de 12 services stadig ikke grep-bare med samme
   udtryk, og så er halvdelen af pointen væk.

## Step 1's resultat (målt 2026-07-31)

Før-målingen er kørt, inden nogen kode er rørt. Den bekræftede diagnosen, men **flyttede
planen på tre punkter** — de står her frem for i Outcome, fordi de ændrer arbejdet der ligger
foran os.

### (i) Mekanikken: 11 af 12, nu målt på alle 12

Proben reproducerer uvicorns egen `dictConfig` inde i det byggede image og importerer
`app.main`:

| root handlers | eff. niveau `app.*` | `info_enabled` | services |
|---|---|---|---|
| `0 []` | WARNING | `False` | account, ai, analytics, banking, budget, categorization, goal, notification, saga, transaction, user (**11**) |
| `1 [StreamHandler]` | INFO | `True` | gateway (**1**) |

`import=ok` for alle 12, så tallene er ikke import-fejl der maskerer sig.

Adfærden er reproduceret uafhængigt på to services, og symptomet er præcis det P3-57
beskrev — bar besked, intet niveau, intet tidsstempel, intet logger-navn:

```
banking-service-1      | Bank callback missing authorization code [a3d6407f]: state=p357probe
banking-service-1      | INFO:     192.168.65.1 - "GET /api/v1/bank/callback?state=p357probe HTTP/1.1" 303 See Other
transaction-service-1  | Rejected oversized POST to /health: 20971520 bytes declared, limit 10485760
transaction-service-1  | INFO:     192.168.65.1 - "POST /health HTTP/1.1" 413 Request Entity Too Large
```

Baseline for alle 12: `grep -c WARNING` = **0** og `grep -c ERROR` = **0**.

### (ii) 5 af 12 har ingen reachable warning at måle på — heller ikke efter fixet

Systematisk gennemgang af hver services API-proces (inbound-adaptere + application-lag,
worker-moduler ekskluderet, da de er egne processer):

| service | reachable warning | trigger |
|---|---|---|
| banking | `bank_api.py:145` | ingen auth |
| transaction | `main.py:64` (size-guard-middleware) | ingen auth, kører før routing |
| analytics | `shared/logging.py:31` via `execute_with_logging` | JWT |
| categorization | `categorization_service.py:91` | `X-Internal-API-Key` |
| gateway | `auth.py:113` | JWT uden `X-Account-ID` |
| ai | `pipeline.py:109` | JWT + `X-Account-ID`, kræver Ollama oppe |
| **account** | **ingen** | kun startup-fejl (`main.py:26`) |
| **user** | **ingen** | kun `logger.info` i request-stien |
| **goal** | **ingen** | **nul logging-statements i hele API-processen** |
| **notification** | **ingen** | alle warnings ligger i consumer-processen |
| **saga** | **ingen** | API'en eksponerer kun `/health` + én read; alt logning er i orchestratoren |
| budget | kun ved upstream-fejl | ikke fremprovokerbar fra request-input |

**Det er et selvstændigt resultat, ikke en besværlighed ved verifikationen.** P3-57's
overskrift er sand, men konsekvensen er ujævn: at give `goal-service` en logging-konfiguration
ændrer ingenting, for der er intet at konfigurere *for*. Fem services har intet at sige om sig
selv i request-stien — det er en observability-mangel som P3-57 ikke dækker og ikke skal
udvides til at dække. **Nyt item, ikke scope-creep her.**

`budget-service` er en fjerde kategori: warnings findes (`analytics_port.py:49`), men fyrer kun
når analytics svarer non-200, og der er ikke request-input der frembringer det —
`InvalidPeriodError` er uopnåelig fra den sti, fordi `budget_period()` altid giver start ≤ slut.
Den kan verificeres ved at stoppe analytics, men det er ikke en ren, gentagelig trigger.

### (iii) `disable_existing_loggers`-fælden er allerede i drift — i account-service

Se [findings/2026-07-31-account-service-log-silenced-by-alembic.md](../findings/2026-07-31-account-service-log-silenced-by-alembic.md).

Kort: `account-service` har **4 logliner på 35 timers uptime** og er samtidig `healthy` med
`restarts=0` og `/health` på 10 ms. Ingen access-log, intet `Application startup complete`.
Årsagen er `alembic/env.py:20`'s `fileConfig(...)`, som defaulter
`disable_existing_loggers=True` — målt i containeren:

```
FØR fileConfig:  uvicorn.access disabled=False handlers=1 | uvicorn.error disabled=False
EFTER fileConfig: uvicorn.access disabled=True  handlers=1 | uvicorn.error disabled=True
```

`account-service` er den eneste af de 12 der kører migrations **i API-processen**
(`app/main.py:33`, fra `lifespan`); de 8 andre alembic-services gør det i CMD, i en tidligere
proces, hvor bivirkningen dør med processen. Grep-verificeret: **9 af 9** `env.py` kalder
`fileConfig`, og **1** — `transaction-service/migrations/env.py:25` — sender
`disable_existing_loggers=False`. Fælden er altså ramt og lukket ét sted før, uden at det blev
en konvention.

**Det ændrer planen konkret: `setup_logging()` alene ville ikke virke i `account-service`.**
Vores kald sker ved import; `fileConfig` kører bagefter i `lifespan` og ville slukke det igen —
og servicen ville se fikset ud i enhver statisk kontrol. Derfor er `env.py` nu et step.

## Beslutninger truffet før planen (godkendt 2026-07-31)

**(a) Ny pakke `services/shared/observability`, ikke en udvidelse af `shared/messaging`.**
Trade-offen er navne-ærlighed mod churn, og churn taber. `shared/messaging` er allerede dep i
9 af 12 services (8 via `pyproject.toml`, `account` via `requirements.txt`-stier), så at
lægge helperen der ville koste to nye deps i stedet for tolv. Men `messaging.logging` som
hjemsted for **API**-logging er et usandt navn i en kodebase hvor bounded contexts og
eksplicitte grænser er den bærende konvention — og et usandt modulnavn er præcis den slags
der får den næste service til at trække `messaging` ind for at logge, og dermed en
MQ-afhængighed den ikke har brug for. Vi accepterer 12 dep-linjer + 12 `COPY`-linjer +
lock-regen som prisen for at pakkens navn kan læses uden fodnote.

**Omkostningen ved (a) er navngivet:** `shared/messaging` beholder
`setup_worker_logging` som en **tynd delegerende shim** til `observability`, så ingen af de
23 worker-kaldsteder ændres i denne plan. Alternativet — at migrere alle 23 nu — gør diffen
uoverskuelig og blander to ting: at give API'erne en konfiguration, og at rydde workernes
imports. Migrationen af kaldstederne bliver et selvstændigt S-item.

**(b) Fuld `dictConfig` der også overtager uvicorns tre loggere**, ikke kun root/`app.*`.
Begrundelsen er færdig-kriteriet: hvis uvicorn beholder sit eget `"INFO:     ..."`-format, så
er access-linjerne stadig ikke grep-bare på niveau, og loggen har to formater — vi ville have
løst 11 services og efterladt den halve fejl i alle 12. Prisen er at verifikationen bliver
dyrere, fordi vi nu kan **regressere** noget der virker: en tavs `uvicorn.error` er værre end
den tilstand vi startede i. Derfor har verifikationen en eksplicit negativ kontrol for
uvicorns egne linjer (se Verification, punkt 3).

**Fælden ved (b), navngivet fordi den er stille:** `logging.config.dictConfig`
defaulter `disable_existing_loggers` til **`True`**. Alle `app.*`-loggere der er oprettet på
modul-niveau i moduler importeret *før* vores kald, ville blive slået fra. Gateway undgik den
uden at vide det, fordi `basicConfig` ikke har den semantik. Vores config **skal** sætte
`disable_existing_loggers: False`, og det skal have sin egen test — ellers shipper vi en
konfiguration der ser rigtig ud og gør logningen værre end i dag. Det er samme fejlform som
det instrumentet handler om, så den skal fanges af en test og ikke af et review.

## Non-goals

- **Ingen ændring af hvad der logges.** Ingen nye `logger.*`-kald, ingen ændrede beskeder,
  ingen fjernede. Kun *hvor* de lander og *hvordan* linjen ser ud.
- **Ingen structured/JSON-logging.** Formatet bliver menneskelæsbar tekst. JSON-logs hører
  til en beslutning om et log-aggregeringslag (P3-11 / Loki), og at afgøre den som
  bivirkning af denne plan ville binde os til et format ingen consumer har bedt om.
- **Ingen migration af de 23 `setup_worker_logging`-kaldsteder.** Shimmen bevarer dem
  uændrede; workerne logger som i dag (og de har allerede en konfiguration — de er ikke
  syge).
- **Ingen request-id/correlation-id.** Ville kræve middleware + contextvars i 12 services;
  eget item.
- **Ingen nye `logger.*`-kald i de 5 services der mangler dem** (→ **P3-59**). Det er den
  ubehagelige version af dette non-goal: for `account`, `user`, `goal`, `notification` og
  `saga` leverer planen en konfiguration til en proces der ikke har noget at logge, og de får
  altså mindre ud af den end de 6 andre. Det er stadig rigtigt at give dem konfigurationen —
  ellers er service nr. 13's første `logger.warning` usynlig igen — men planen påstår ikke at
  den gør dem observerbare.
- **Ingen ændring af `serverless-health-job`.** Den kører `python -m app.main run`, har ingen
  logging-konfiguration og er ikke en af de 12 API-processer. Nævnt her så det er et fravalg
  og ikke en overset service.
- **`LOG_LEVEL`-defaulten forbliver `INFO`** i alle 12. Vi gør en dead config levende; vi
  vælger ikke et nyt niveau.

## Steps

Commits følger `feedback_commit_per_fase`: én commit per logisk fase, så en rollback kan
ramme præcist.

1. [x] **Måle før-tilstanden og gemme den** — ingen kodeændring. **Kørt 2026-07-31; resultatet
   står i [Step 1's resultat](#step-1s-resultat-målt-2026-07-31)** og har omskrevet Goal,
   tilføjet step 2 og afledt to nye backlog-items. Bemærk at forventningen "trig en kendt
   warning i hver af de 12" ikke holdt: 5 services har ingen, og det var ikke til at vide uden
   at måle.

2. [x] **`disable_existing_loggers=False` i alle 9 `env.py`** — egen commit, *før* pakken, så
   den kan verificeres isoleret: `account-service` skal gå fra 4 linjer til at have en
   access-log, og det sker uden at nogen ny kode er indført. Præcedensen er
   `transaction-service/migrations/env.py:25`, som allerede gør det; de 8 andre (`account`,
   `banking`, `budget`, `categorization`, `goal`, `notification`, `saga`, `user`) får samme
   argument. De 8 er harmløse i dag alene i kraft af deres procesopdeling — og P3-17 er ved at
   ændre procesopdelingen, så det er et værn og ikke kosmetik.

3. [x] **Ny pakke `services/shared/observability/`** — `pyproject.toml` (hatchling,
   `name = "finans-tracker-observability"`, `version = "0.1.0"`, ingen runtime-deps ud over
   stdlib), `observability/__init__.py`, `observability/logging.py`,
   `observability/py.typed` (obligatorisk per CLAUDE.md — uden markøren degraderer alt fra
   pakken til `Any` i hver forbrugende service, og typecheck-gaten bliver grøn på præcis den
   bug den findes for at fange). Kopiér `shared/auth/pyproject.toml` som skabelon.

   API: `setup_logging(level: str | int | None = None) -> None`. Bygger en `dictConfig` med
   `disable_existing_loggers: False`, én `StreamHandler` til stderr på root, formatet fra
   `shared/messaging` (`"%(asctime)s %(levelname)-8s [%(name)s] %(message)s"` — det er det
   mest udbredte af de tre, 23 kaldsteder mod gateways 1, så det er den mindste ændring for
   log-pipelines), og eksplicitte entries for `uvicorn`, `uvicorn.access`, `uvicorn.error`
   med `propagate: True` og ingen egne handlers, så de arver root's formatter. `level=None`
   ⇒ `os.getenv("LOG_LEVEL", "INFO")`.

4. [x] **Tests for pakken** — `services/shared/observability/tests/test_logging.py`. Fire
   tests, hvor de to første er de vigtige:
   - en logger oprettet **før** `setup_logging()` logger stadig efter (vagten mod
     `disable_existing_loggers`-fælden fra afsnittet ovenfor);
   - `app.x.logger.info` er enabled efter kaldet, og record'en formateres med niveau,
     tidsstempel og navn (assertér på formatteren, ikke på capsys, så testen ikke afhænger af
     pytests egen log-capture);
   - `uvicorn.access` har ingen egne handlers og propagerer;
   - idempotens: to kald giver stadig én handler på root.

5. [x] **`messaging.setup_worker_logging` bliver en delegerende shim** —
   `shared/messaging/messaging/logging.py` kalder `observability.setup_logging`, beholder sin
   signatur (`(name, level=INFO) -> Logger`) og sin `LOG_FORMAT`-konstant som re-export, så
   `shared/messaging/tests/test_logging.py` og de 23 kaldsteder er uændrede.
   `shared/messaging/pyproject.toml` får `observability` som dep, og **versionen bumpes** —
   path-deps installeres som kopier, så uv genopretter dem ikke ved uændret version
   (CLAUDE.md).

6. [x] **De 12 API-processer** — én commit, eller to hvis diffen bliver uoverskuelig
   (`pyproject`/`Dockerfile`-churn separat fra `main.py`-kaldene). Per service:
   - `pyproject.toml`: `observability` som path-dep (`account-service`:
     `requirements.txt` får `../shared/observability`, samme mønster som dens tre andre);
   - `Dockerfile`: `COPY services/shared/observability /shared/observability` ved siden af de
     eksisterende shared-COPY'er;
   - `app/main.py`: `setup_logging(...)` **på modul-niveau, før første `logger`-oprettelse**
     — ikke i `lifespan`, hvor det ville køre efter alle importer og dermed for sent til
     modul-niveau-loggere. De 7 services der erklærer `LOG_LEVEL` i `config.py` sender den
     ind eksplicit (`setup_logging(settings.LOG_LEVEL)`), så deklarationen bliver levende og
     ikke bare tilfældigvis matcher env-fallbacken; de 5 uden kalder `setup_logging()`.
   - `gateway-service/app/main.py`: de fem linjer `basicConfig` erstattes af `setup_logging(LOG_LEVEL)`.
     **Gateway migreres til sidst**, fordi den er før/efter-kontrollen — så længe den er
     urørt, er den et fast punkt at måle imod.
   - `uv lock` per service.

7. [x] **`make -C services/<svc> check`** (lint + typecheck + test) for de 11 services på
   gaten, `make -C services/account-service test` for account. Nyt shared-modul ⇒
   `TYPECHECK_SERVICES` skal fortsat være grøn; en manglende `py.typed` vil vise sig som
   `Any`-degradering og ikke som en fejl, så step 2's markør er ikke valgfri.

8. [x] **Verification** — se næste afsnit. Egen commit for eventuelle rettelser den afdækker.

9. [x] **Docs** — `BACKLOG.md`-rækken → `done 2026-07-31` + link hertil, `STATUS.md`,
   `00-INDEX.md`, session-log, og planens **Outcome** med begge målings-tabeller.
   CLAUDE.md's kode-stil-afsnit får en linje om at nye services kalder `setup_logging()` i
   `app/main.py` — ellers gentager fejlen sig ved service nr. 13, og det er den *eneste*
   måde denne plan ikke skal laves igen.

## Verification

Statisk grønt beviser intet her: `make check` importerer ikke `app.main` under uvicorn, så
hele fejlklassen ligger uden for dens rækkevidde (CLAUDE.md siger det direkte). Verifikationen
er derfor i den kørende stak. Efter step 1 har den fem dele, og rækkefølgen er bevidst: den
universelle først, den selektive bagefter.

1. **Alle 12: access-linjen bærer niveau, tidsstempel og logger-navn.** `docker compose up
   --build`, vent på at healthchecken har pollet, og læs én access-linje per service. Før:
   `INFO:     192.168.65.1 - "GET /health HTTP/1.1" 200 OK` (uvicorns eget format, intet
   logger-navn). Efter: samme information i husets format. **Dette er det eneste
   adfærdsmæssige kriterium der dækker alle 12**, og det er grunden til at beslutning (b) ikke
   må rulles tilbage uden at kriteriet også skifter.

2. **`account-service` specifikt: fra 4 linjer til en levende log.** Kravet er skarpere end
   "der kommer linjer": access-logs skal komme **efter** at `lifespan` har kørt migrations,
   for det er dér `fileConfig` slog dem ud. En før/efter der kun ser på opstartslinjerne
   ville være grøn uden at fixet virkede. Mål med `docker compose logs account-service | grep
   -c "GET /health"` — før: **0** efter 35 timers uptime.

3. **De 6 med reachable warning: `grep -c WARNING` 0 → ≥1 på samme trigger.**
   banking (`?state=p357probe`) og transaction (413-guarden) er de to uden auth og køres
   altid; analytics, categorization, gateway og ai kræver credentials og køres hvis de er ved
   hånden. De 5 uden reachable warning **kan ikke verificeres adfærdsmæssigt og skal ikke
   påstås at være** — for dem er punkt 1 og den mekaniske probe hele beviset. At skrive andet
   i Outcome ville være et overclaim.

4. **Negativ kontrol for uvicorn — den del beslutning (b) kan regressere.** Efter ændringen
   skal `uvicorn`s startup-linjer, `uvicorn.access`-linjerne **og** en `uvicorn.error`-linje
   stadig komme. Access dækkes af punkt 1; `uvicorn.error` fremprovokeres med en request der
   kaster. **En tavs `uvicorn.error` er en regression af planen, ikke en bivirkning** — det er
   den ene måde dette fix kan gøre skade.

5. **Verificér at gaterne kan blive røde.** To mutationer, ikke én:
   - `disable_existing_loggers: True` i `observability/logging.py` ⇒ step 4's første test skal
     blive rød;
   - rul `disable_existing_loggers=False` tilbage i `account-service/alembic/env.py` ⇒
     access-logs skal forsvinde igen. Det er den mutation der beviser at punkt 2 måler fixet
     og ikke bare en genstartet container.

   En test for en fælde, der ikke er set fejle, er en død annotation
   (`feedback_dead_suppression_annotations`).

6. `make test-e2e` som regressionsværn: 12 services får en modul-niveau-ændring i `main.py`,
   og en importfejl dér er en container der ikke starter.

## Risks & rollback

- **`disable_existing_loggers` slukker `app.*`-loggere.** Værste udfald: vi gør logningen
  værre end i dag, og det ser ud som succes fordi *nogle* linjer kommer. Fanget af step 4's
  første test + mutationerne i Verification 5. Fælden er ikke hypotetisk — den er allerede i
  drift i `account-service`, se Step 1's resultat (iii).
- **Uvicorns loggere bliver tavse.** Fanget af Verification 4. Rollback: fjern de tre
  `uvicorn*`-entries fra configen, og vi lander på beslutning (b)'s afviste alternativ (kun
  root/`app.*`) — som er en fungerende delmængde, ikke en brækket tilstand. Det gør (b)
  billig at trække tilbage.
- **En service starter ikke efter dep/COPY-ændringen.** Mest sandsynlige konkrete fejl i hele
  planen: 12 × (`pyproject` + `Dockerfile` + `uv lock`) er mekanisk arbejde med en
  glemme-en-linje-fejlmode, og `make check` fanger den ikke (CLAUDE.md: statisk check
  importerer ikke `app.main` under imagets versioner). Fanget af `up --build` + Verification 5.
  Rollback per service, fordi step 5 er én commit per fase.
- **Log-volumen stiger.** 11 services går fra `WARNING` til `INFO` i praksis. Det er hele
  formålet, men det kan overraske i en lokal `docker compose logs -f`. `LOG_LEVEL=WARNING` i
  env er ventilen, og den virker nu i alle 12 — hvilket den ikke gjorde før.
- **Rollback samlet:** planen tilføjer en pakke og rører ellers kun `main.py`-toppe,
  `pyproject`/`Dockerfile` og locks. Ingen migrations, ingen event-kontrakter, ingen
  API-overflade. `git revert` af fase-commits er tilstrækkeligt, i omvendt rækkefølge.

## Outcome

**Shippet 2026-07-31.** Fire commits: `772a891d` (env.py ×8), `4d2db80c` (pakken),
`31c15ca6` (messaging-shim), `3cf32022` (de 12 services). Step 1's egne fund står i
[Step 1's resultat](#step-1s-resultat-målt-2026-07-31) og gentages ikke her.

### Resultatet, målt i den kørende stak (52 containere)

| kriterium | før | efter |
|---|---|---|
| access-linje med niveau + tidsstempel + logger-navn | 0 af 12 | **12 af 12** |
| app-niveau `WARNING` grep-bar med fuldt format | 0 | **4 målt** (banking, transaction, categorization, analytics) |
| app-niveau `INFO` når loggen | 0 (dødt overalt) | **2 målt** (account, user) |
| `uvicorn.error` lever (negativ kontrol) | ja | **ja** |
| workernes format | uændret | **uændret**, millisekunder bevaret |

Eksempel på det der før var uskelnelig stdout-støj:

```
før:   Bank callback missing authorization code [a3d6407f]: state=p357probe
efter: 2026-07-31 00:06:29,354 WARNING  [app.adapters.inbound.bank_api] Bank callback missing authorization code [34217992]: state=p357after
```

### Planens forudsigelse om account-service holdt, og den kostede et ekstra greb

Planen sagde at `account-service` ville være den ene service hvor fixet leveres og ikke
virker. Det skete præcis sådan, og det var **ikke** fanget af step 2: `disable_existing_loggers=False`
forhindrer at loggere *slukkes*, men `fileConfig` **erstatter** stadig root-handleren med
`alembic.ini`'s (`%(levelname)-5.5s [%(name)s]`, intet tidsstempel) og sætter root til `WARN`.
Vores kald sker ved import, alembic kører bagefter i `lifespan`.

Det viste sig i loggen som et skift midt i opstarten — og det var **den manglende linje**,
ikke formatet, der afslørede omfanget:

```
2026-07-31 00:03:15,930 INFO     [uvicorn.error] Started server process [1]   ← vores config
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.                 ← alembic overtog
INFO  [uvicorn.access] 127.0.0.1 - "GET /health HTTP/1.1" 200                  ← intet tidsstempel
(og "Database migrations applied successfully" udgik helt: root er nu WARN)
```

Fixet er `_reassert_logging()` efter migrationen, i begge grene. **Den generelle lektie er
værd at holde fast på: at rette `disable_existing_loggers` var nødvendigt men ikke
tilstrækkeligt.** Enhver `fileConfig`/`dictConfig` i samme proces er en fuld
rekonfiguration, ikke et delta — så spørgsmålet er aldrig "slukker den noget", men "hvem
konfigurerede sidst". P3-17 fjerner behovet ved at tage migrations ud af API-processen, og
det er den rigtige langsigtede løsning; `_reassert_logging` er et plaster med en
item-reference.

### Det overclaim der næsten kom med

En probe der sendte ugyldig HTTP til alle 12 porte gav **12 × `grep -c WARNING` 0 → 1**, og
det var lige ved at blive planens hovedresultat: et adfærdsmæssigt før/efter der dækker alle
12, inklusive de 5 uden app-logning. Kontrollen viste at det er **tilfældigt rigtigt**.
Reproduceret i før-tilstanden:

```
uvicorn.error:  WARNING:  Invalid HTTP request received.     ← indeholder "WARNING"
app.probe:      app-niveau warning                            ← bar besked
```

uvicorns eget format har altid haft niveauet i teksten, så `grep WARNING` fandt uvicorns
warnings også før. Det ægte før/efter findes **kun på app-niveau**; for uvicorn-linjerne er
gevinsten format og logger-navn, ikke greppability. Det er samme fælde som
`feedback_baseline_can_be_accidentally_right`, bare med fortegnet vendt: her var det
*efter*-målingen der var tilfældigt flatterende.

Det ændrer ikke konklusionen — de 12 services har nu ét format, og access-linjen bærer
logger-navn i alle 12 — men det ændrer *hvad* der er bevist, og forskellen er hele forskellen
mellem en måling og en påstand.

### Bivirkning der er en gevinst

`saga-service` har nul logging-statements i sin API-proces (P3-59), men får nu alligevel en
grep-bar, tidsstemplet `WARNING  [uvicorn.error] Invalid HTTP request received.` Det er
argumentet for beslutning (b) i praksis: ved at tage uvicorns loggere med, har selv de fem
tavse services et minimum af observerbarhed de ikke havde før.

### Afvigelser fra planen

- **Step 2 blev delt fra P3-57 til sit eget item (P3-58)** undervejs, fordi fundet er
  selvstændigt og har egen finding-note.
- **`_reassert_logging` i account-service var ikke i planen.** Den er en konsekvens af step
  1 (iii)'s fund, som planen forudsagde kvalitativt men ikke i mekanisme.
- **Verifikationen af de 6 warning-triggere blev 4, ikke 6.** `gateway`s
  `auth.py:113` fyrede ikke: proben-brugeren *har* en `Default Account`, fordi registrering
  opretter én via sagaen, så betingelsen kræver en bruger med nul konti. `ai` kræver
  Ollama-routing der lykkes først (P3-46 gør den upålidelig under fuld stak). Ikke
  verificeret ≠ virker ikke, og de står som ikke-verificerede frem for antaget grønne.
- **`make test` for `account-service` kunne ikke køres** (`pytest: command not found`) —
  P3-39, uændret, prøvet frem for gentaget som forbehold.

### Følger

- **P3-59** (fem services uden logning i request-stien) er nyt og er den direkte fortsættelse.
- **P3-17** får et konkret argument mere: `_reassert_logging` findes kun fordi migrations
  kører i API-processen.
- **CLAUDE.md** har nu en linje om at nye services kalder `setup_logging()` i `app/main.py`.
  Det er den eneste grund til at denne plan ikke skal laves igen ved service nr. 13.
