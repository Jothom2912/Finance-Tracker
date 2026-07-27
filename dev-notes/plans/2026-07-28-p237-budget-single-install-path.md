---
title: "P2-37: én install-sti per service — budget-service på uv sync --frozen"
date: 2026-07-28
status: done
backlog-items: [P2-37]
related:
  - findings/2026-07-27-none-annotation-204-fastapi-split.md
  - plans/2026-07-27-p231-static-typecheck-gate.md
---

# P2-37: én install-sti per service — budget-service på `uv sync --frozen`

## Goal

Budget-services image skal installere fra `uv.lock` — den samme fil som dens tests og dens
mypy-gate læser — så der ikke længere findes to uenige sandhedskilder for én afhængighed.
Færdig når: `services/budget-service/requirements.txt` er slettet, imaget bygger med
`uv sync --frozen --no-dev`, containeren og alle tre workers *starter og svarer* (ikke kun
bygger), og en vagt i CI fejler hvis en service igen har både `uv.lock` og `requirements.txt`.

Målestokken er ikke "grøn `make check`" — det var netop et grønt `make check` der udstedte det
døde image i `71476703`. Se **Verification**.

## Context

P2-31 lukkede med at budget-services image døde ved import mens hele test- og typecheck-suiten
var grøn: `from __future__ import annotations` + `-> None` + FastAPI 0.115.0 = assertion på en
204-rute. Fixet dér (`response_model=None`) behandlede symptomet bevidst, fordi roden —
`uv.lock` styrer tests, `requirements.txt` styrer imaget — er dette item.
[Finding](../findings/2026-07-27-none-annotation-204-fastapi-split.md).

Målt 2026-07-28 (og det korrigerede fundets oprindelige formulering, som påstod at `make freeze`
fandtes overalt og bare ikke blev checket — begge led var usande):

| Install-sti i imaget | Services |
|---|---|
| `uv sync --frozen --no-dev` | 9 — ai, analytics, categorization, gateway, goal, notification, saga, transaction, user |
| `pip install -r requirements.txt` | 3 — account, banking, budget |

Drift-betingelsen er at *begge* filer findes. Verificeret med en scan over `services/*/`:
det gælder **præcis én** service, budget. account og banking har ingen lockfile — de kan ikke
drifte, de har én usandt-låst kilde i stedet for to uenige. Deres sti er P3-23/P3-01, ikke denne
plan.

`freeze:`-targets findes i 3 af 15 services (transaction, categorization, user). Alle tre bygger
med `uv sync --frozen` og har **ingen `requirements.txt` på disk** — targets der genererer en fil
ingen læser. Levn fra før Dockerfile-migrationen.

## Non-goals

- **Ingen adfærdsændring i budget-domænet.** Ingen `app/`-fil røres, med den ene mulige
  undtagelse at 204-kommentarerne i `rest_api.py` og `monthly_budget_api.py` henviser til
  `requirements.txt`-pinnet som forsvinder — de opdateres tekstuelt, `response_model=None`
  bliver stående (den er korrekt under begge FastAPI-versioner og er den eksplicitte form).
- **account og banking flyttes ikke.** De hører under P3-23/P3-01.
- **`uv.lock` genereres ikke om.** Locken er i sync (`uv lock --check` grøn) og dens indhold er
  allerede det testene kører mod. Vi ændrer hvem der læser den, ikke hvad den siger.
- **Ingen ny mypy-scope.** `packages = ["app"]` står uændret; `tests/` er stadig utypechecket
  (P3-41).
- **Ingen ADR.** Dette er ikke en arkitektur-beslutning, det er konvergens mod en form 9 services
  allerede har.

## Steps

### 1. [x] Dockerfile → `uv sync --frozen --no-dev`

`services/budget-service/Dockerfile`. Kopiér formen fra `services/transaction-service/Dockerfile`
med **én afvigelse**: budget har fire shared-pakker (transaction har tre — ingen `domain`).

```
+ COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/
  ENV ... + UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
  COPY services/shared/{contracts,auth,messaging,domain} /shared/...   # uændret
- COPY services/budget-service/requirements.txt .
- RUN pip install --no-cache-dir -r requirements.txt /shared/...
+ COPY services/budget-service/pyproject.toml services/budget-service/uv.lock ./
+ RUN uv sync --frozen --no-dev
```

Den ikke-åbenlyse del, værd at forstå frem for at kopiere: `pyproject.toml` erklærer shared som
`path = "../shared/auth"`. Med `pyproject.toml` i `/app` opløses det til `/shared/auth` — derfor
kopieres de dertil og ikke ind under `/app`. `PATH="/app/.venv/bin:$PATH"` er det der gør at
compose-workernes `command: ["python", "-m", ...]` rammer venv'en; uden den kører de systemets
python uden dependencies. Begge er de to steder denne Dockerfile kan gå i stykker stille.

### 2. [x] Slet `services/budget-service/requirements.txt`

Éт-fils-sletning. Efter trin 1 er der ingen læser tilbage (verificeret: kun Dockerfilens to
linjer refererede den, plus tre kommentarer).

### 3. [x] Slet de 3 døde `freeze:`-targets

`services/{transaction,categorization,user}-service/Makefile` — 2 linjer hvert sted (+ evt. en
`help`-linje). De genererer en fil ingen af de tre har eller læser. Egen commit: det er en
anden service-trio end trin 1-2, og skal kunne revertes uafhængigt.

### 4. [x] Vagt mod at fejlklassen kommer tilbage

`scripts/compose_check.py` → ny check: en service-mappe må ikke have både `uv.lock` og
`requirements.txt`.

**Besluttet 2026-07-28: (a).** Backlog-rækken siger
`compose_check.py`, men scriptets docstring erklærer eksplicit sit scope som
`docker-compose.yml`, og denne check læser `services/*/` på disk. To muligheder:

- **(a) Udvid `compose_check.py`** — omskriv docstring + navn-narrativ til "build-hygiejne", så
  scriptet dækker to regler. Billigst: det kører allerede i `ci.yml:52`, i `make compose-check`
  og i pre-commit. Ingen ny wiring, ingen ny fil at glemme.
- **(b) Nyt `scripts/install_path_check.py`** — ærligt scope per script, men kræver Makefile-target,
  et CI-step og en `help`-linje, og bliver den fjerde `*_check.py` med samme boilerplate.

**Valgt (a)**, og grunden er at trin 4's værdi er *at den kører*, ikke at den bor pænt:
fejlklassens symptom er en grøn kørsel, så en vagt der ikke er wired op er værre end ingen. Prisen
er at et script navngivet efter compose får en check der ikke handler om compose — betalbart med
en omdøbning af docstring-scopet, dyrt hvis vi lader navnet lyve. Hvis vi tager (a), hedder
konsekvensen at scriptet på sigt er `build_hygiene_check.py`; det er en omdøbning, ikke et
redesign.

### 5. [x] Verification — se næste sektion. Egen commit til noter/Outcome.

Commit-rækkefølge: (1) Dockerfile + slet requirements + kommentar-opdatering · (2) døde
freeze-targets · (3) vagt i check-scriptet · (4) noter. Trin 1 er den eneste med runtime-risiko,
og den er dermed den eneste der skal revertes hvis noget brænder.

## Verification

Rækkefølgen er valgt så det billigste bevis kommer først, men **ingen af de tre første beviser
noget om det der fejlede sidst** — kun trin D gør.

- **A. `make -C services/budget-service check`** — lint + format + mypy. Uændret grøn forventet;
  den rører ikke locken.
- **B. `make -C services/budget-service test`** — 117 tests (61 unit + 56 integration). Samme:
  de kørte allerede mod locken, så de skal være uændrede. *Hvis de ændrer sig, er præmissen for
  hele planen forkert* og vi stopper.
- **C. `docker compose build budget-service`** — beviser at `uv sync --frozen` kan opløse fire
  path-deps i imaget. Den fejler højt hvis locken og pyproject er uenige.
- **D. Containeren og de tre workers starter og svarer.** Det er *dette* trin der er hele itemet;
  A-C var alle grønne den nat imaget var dødt.
  - `docker compose up -d budget-service` → `docker compose logs budget-service` viser `alembic
    upgrade head` gennemført og uvicorn lyttende, **ingen traceback**.
  - `curl -s -o /dev/null -w '%{http_code}' localhost:8003/health` → 200.
  - De tre 204-ruter rammes faktisk (det var dem der døde ved *import*, så en levende `/health`
    er allerede stærk evidens, men ruterne er billige at ramme).
  - `docker compose up -d budget-outbox-worker budget-month-close-scheduler
    budget-alert-scheduler` → alle tre logger deres loop-start uden `ModuleNotFoundError`.
    Dette er `PATH`-halvdelen af trin 1 og kan ikke udledes fra at API'et virker.
- **E. Kontrol, ikke kun treatment.** Vagten fra trin 4 skal bevises i stand til at blive rød:
  `touch services/transaction-service/requirements.txt` → `make compose-check` **skal** fejle →
  slet filen igen → grøn. En grøn vagt beviser ingenting om vagten. (Dette er lektien fra
  `verify-typecheck-gate` og fra P3-40.)
- **F. `make test-e2e`** før commit af trin 1 — det var e2e der fangede den døde container sidst,
  og budget deltager i ADR-0003-kæden.

Ikke gennem `tail`/`head`: pipelinens exit-kode er sidste kommandos, så `check | tail && commit`
committer på et fejlende check. Er sket 2×.

## Risks & rollback

**Den reelle risiko er ikke Dockerfile-formen — det er at alle 13 deployede dependencies bumper
på én gang.** Målt:

| | requirements (deployet i dag) | uv.lock (bliver deployet) |
|---|---|---|
| fastapi | 0.115.0 | 0.136.3 |
| uvicorn | 0.30.0 | 0.49.0 |
| pydantic | 2.9.0 | 2.13.4 |
| pydantic-settings | 2.5.0 | 2.14.1 |
| sqlalchemy | 2.0.36 | 2.0.50 |
| asyncpg | 0.30.0 | 0.31.0 |
| psycopg2-binary | 2.9.10 | 2.9.12 |
| alembic | 1.14.0 | 1.18.4 |
| httpx | 0.27.2 | 0.28.1 |
| python-jose | 3.3.0 | 3.5.0 |
| redis | >=5.0.0 → 5.x | 8.0.0 |
| aio-pika | (upinnet) | 9.6.2 |
| fastapi-cache2 | 0.2.2 | 0.2.2 |

Det er præcis det `71476703` afviste at gøre ("ville ændre hele servicens deployede
afhængighedssæt i ét hug"). Forskellen nu er at det er *hele* itemet frem for en sidegevinst ved
et hastefix, og at retningen af tillid er rigtig: locken er det sæt de 117 tests og mypy-gaten
allerede kører imod. Vi flytter imaget hen til det verificerede sæt, ikke omvendt.

De to bump med reel semantisk risiko:

- **httpx 0.27 → 0.28** — `content=`/`data=`-deprecations og ændret default for `verify`.
  Budget kalder analytics' `/overview` (P1-13). Dækket af integrationstestene via `respx`, men
  respx mocker transporten, så en ægte-netværks-forskel ville ikke ses dér. Trin D's e2e er det
  der fanger den.
- **redis 5 → 8** — `fastapi-cache2 0.2.2` er upinnet mod redis-major og er den mest sandsynlige
  inkompatibilitet i tabellen. Symptomet ville være caching der fejler ved *første* request, ikke
  ved import — altså synlig i trin D, ikke i trin C.

**Detektion:** trin D's logs og e2e. Fejlmoden vi frygter er en container der bygger og starter
men fejler på første rigtige kald — derfor er `/health` alene ikke nok, og derfor står F i listen.

**Rollback:** trin 1 er én commit der rører én Dockerfile og sletter én fil. `git revert` giver
det nuværende, kendt-fungerende (om end usandt-låste) image tilbage. Trin 2-4 er uafhængige og
har ingen runtime-flade. Der er ingen data-migration og ingen event-kontrakt involveret, så
rollback er ren.

**Hvad vi accepterer som omkostning:** budget-services deployede afhængighedssæt springer et
halvt års versioner på én gang, og vi opdager en eventuel inkompatibilitet i verifikationen
frem for gradvist. Det er acceptabelt fordi alternativet — at bumpe requirements.txt ét pin ad
gangen — bevarer den todelte sandhedskilde, altså selve fejlklassen, mens man arbejder.
Én stor verificeret bump slår et halvt år med to uenige filer.

## Outcome

**Landet 2026-07-28** over tre commits, uden afvigelser fra planen:

- `560cd54a` — budget-services Dockerfile på `uv sync --frozen --no-dev`, `requirements.txt`
  slettet, de tre 204-kommentarer omskrevet.
- `8d7c8f59` — de tre døde `freeze:`-targets slettet (transaction, categorization, user).
- `18bd5fc8` — rule 4 i `scripts/compose_check.py` + docstring/help/CI-stepnavn omskrevet til
  build hygiene.

### Verifikationen, og hvad den faktisk beviste

Planen forudsagde at A/B/C (`check`, `test`, `build`) ville være grønne og *utilstrækkelige*, og
det holdt: `make check` grøn, 117 tests (61 unit + 56 integration) grønne og **uændrede** — hvilket
var planens abort-betingelse, ikke dens succeskriterium — og imaget byggede.

Beviset er trin D. Imaget rapporterer nu `fastapi 0.136.3` mod `0.115.0` før, `app.main`
importerer, og **alle tre 204-ruter registrerer** — den præcise fejlmode fra `71476703`, bevist
fraværende under det sæt der deployes. I compose: alembic kørt, `/health` 200, ren
shutdown+genstart, og alle tre workers oppe (outbox publicerer, month-close ticker).

Den ene verifikation der gav mere end forventet: **alert-scheduleren laver rigtige
httpx-0.28.1-kald** til `analytics/overview` og categorization → 200 OK. Det var netop den bump
planen udpegede som udækket, fordi `respx` mocker transporten og derfor ikke kan se en
ægte-netværks-forskel. Den behøvede ingen særskilt test — den kørte af sig selv, fordi
scheduleren ticker. 24 e2e grønne.

Vagten er verificeret som **kontrol, ikke kun treatment**: rød på transaction med en indsat
`requirements.txt`, rød på budget hvor fejlen faktisk var, grøn igen efter oprydning. Summary-linjen
tæller de 15 inspicerede service-mapper, så "fandt intet at kigge på" ikke kan forveksles med
"fandt noget rent".

### Redis-risikoen viste sig at være mindre — og afdækkede noget andet

Planen udpegede `redis 5 → 8` mod upinnet `fastapi-cache2` som den mest sandsynlige
inkompatibilitet. Den er reelt mindre end antaget, men grunden er ikke betryggende:
**ingen rute i budget-service er dekoreret med `@cache`.** `FastAPICache.init()` kaldes i lifespan
med en `RedisBackend`, og så bruges den ikke. Risikofladen var derfor kun `init` + `aclose()`,
og begge er bevist (startup complete, ren shutdown). → **P3-42**.

### Én residual, målt frem for antaget

Den lokale venv kører **Python 3.14**, imaget **3.11**. Det er samme *form* som den fejlklasse
dette item lukker — tests og image på forskellige forudsætninger — så jeg tjekkede frem for at
antage: locken har nul `python-version`-markers og ingen dublerede pakkenavne, så begge
interpretere resolver til **samme versionssæt**. Formen er bekymrende, denne lock er det ikke.
Bliver den nogensinde delt af en marker, er dette stedet at huske hvorfor.

### Efterladt til andre items

`account` og `banking` er stadig `pip install -r requirements.txt` uden lockfile. De kan ikke
*drifte* — de har én usandt-låst kilde i stedet for to uenige — så de ligger uden for dette item
og hos P3-23/P3-01. Konsekvensen er værd at sige højt: **bankings `fastapi==0.115.0`-pin er den
samme fælde budget lige havde**, og den udløses den dag banking kommer på typecheck-gaten og
nogen tilføjer et `-> None`.
