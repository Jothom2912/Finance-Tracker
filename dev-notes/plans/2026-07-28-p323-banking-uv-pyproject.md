---
title: "P3-23: banking-service på uv + pyproject — lockfile, dev-split og typecheck-gate"
date: 2026-07-28
status: done
backlog-items: [P3-23]
related:
  - plans/2026-07-28-p237-budget-single-install-path.md
  - plans/2026-07-27-p231-static-typecheck-gate.md
  - findings/2026-07-27-none-annotation-204-fastapi-split.md
  - findings/2026-07-26-product-surface-sweep.md
---

# P3-23: banking-service på uv + pyproject

## Goal

banking-service skal have samme dependency-form som de 10 services P2-37 efterlod: én
`pyproject.toml` med et runtime/dev-split, én `uv.lock` som både image, tests og mypy læser, og
navnet på typecheck-gatens allowlist.

Færdig når alle fem holder:

1. `services/banking-service/requirements.txt` er slettet; `pyproject.toml` + `uv.lock` findes.
2. Imaget bygger med `uv sync --frozen --no-dev`, og **API + alle fire workers starter og
   svarer** — ikke kun bygger.
3. `banking-service` står i `TYPECHECK_SERVICES` i `ci.yml`, og `uv run mypy` er grøn.
4. `make -C services/banking-service test` og `lint` virker **lokalt**, ikke kun i CI.
5. `python-jose` er ude af runtime-afhængighederne.

Punkt 3 er den egentlige gevinst: uden den beskytter P2-31 ikke den service hvis bug motiverede
den. Punkt 2 er målestokken, fordi et grønt `make check` netop var det der udstedte det døde
image i `71476703`.

## Context

P2-37 lukkede med **10 af 12** services på `uv.lock`. banking er en af de to tilbagestående, og
den er den værste af de to at lade ligge. Målt 2026-07-28 på `b8cec670`:

**(a) Den bærer fejlklassen P2-31 blev bygget for.** `requirements.txt:1` pinner
`fastapi==0.115.0` — samme pin budget lige blev befriet fra. Jeg har verificeret at fælden ikke
er *armeret* i dag: ingen rute i `app/` annoterer `-> None` (`disconnect_bank` returnerer
`-> dict`, `bank_api.py:262`), så der er ingen 204-assertion at udløse nu. Pinnet er hvad der
ville gøre en fremtidig `-> None` til en deploy-tids-fejl i stedet for en lint-fejl — og banking
kan ikke komme på gaten der ville fange den, fordi der ikke er nogen `pyproject.toml` at hænge
`[tool.mypy]` op i.

**(b) CVE-bæreren er en test-afhængighed i runtime-listen.**
`requirements.txt:10` pinner `python-jose[cryptography]==3.3.0` (P3-26's to CVE'er). Den bruges
**ét sted i hele servicen**: `tests/integration/test_bank_api.py:32`. App-koden signerer med
PyJWT (`app/adapters/outbound/enable_banking_client.py:12`, `import jwt as pyjwt`). Så den
sårbare pakke installeres i produktionsimaget udelukkende fordi der ikke er noget dev/runtime-
split at lægge den i. Det er P3-26's banking-halvdel, løst som biprodukt af formen.

**(c) `aiosqlite` står i runtime-listen med en seks-linjers undskyldning** i en kommentar, der
selv slutter med "banking has no pyproject, so it belongs here". Gælden er selvdokumenterende.

**(d) Fire shared-pakker, tre mekanismer.** `auth` og `messaging` er path-deps i
`requirements.txt`; `contracts` installeres som et løst argument til `pip install` i
`Dockerfile:11`; lokalt og i CI leveres `contracts` i stedet via `PYTHONPATH` (`makefile:8`,
`ci.yml:81`). banking importerer `contracts`, `auth` og `messaging` — ikke `domain`. Alle fire
shared-pakker har `py.typed`, så der er intet der blokerer den installerede form.

CI behandler i forvejen banking som et særtilfælde: `ci.yml:104-105` er `elif [ -f
requirements.txt ]`-grenen, som kun account og banking rammer. Når begge er væk kan grenen dø,
men det er P3-01's afslutning, ikke denne plans.

## Non-goals

- **Ingen adfærdsændring i banking-domænet.** Ingen fil under `app/` røres for at ændre logik.
  Undtagelsen er hvis mypy i trin 4 afdækker en usand annotation: den rettes som *annotation*,
  og hvis en rettelse kræver en logikændring, stopper jeg og lægger den som eget item — det var
  præcis udbyttet af P2-31 (usande kontrakter, ikke typefejl) og det fortjener sin egen commit.
- **`account-service` flyttes ikke.** Den har samme form, men er viklet ind i P3-01's større
  refactor. Vi accepterer bevidst at inkonsistensen består i én service et stykke tid — se
  **Risks**.
- **Ingen dependency-scanning.** Dependabot/`pip-audit` er P3-26 og bliver ikke installeret her.
  Vi fjerner én af dens to konkrete banking-pins fra runtime; den anden (`fastapi`) bliver til
  et floor, ikke et scannet artefakt.
- **Ingen ny mypy-scope.** `packages = ["app"]` som de otte andre. `tests/` forbliver
  utypechecket (P3-41).
- **Ingen ADR.** Dette er konvergens mod en form 10 services allerede har, ikke en beslutning.
- **`tests/integration/test_bank_api.py` omskrives ikke til PyJWT.** `python-jose` flytter til
  dev-gruppen på en ikke-sårbar version. At fjerne den helt er rigtigt, men det ændrer en test i
  samme commit som install-stien, og så er en rød test ikke længere attribuerbar.

## Steps

### 1. `pyproject.toml` + `uv.lock`, `requirements.txt` slettet (commit 1)

- **Ny** `services/banking-service/pyproject.toml`, modelleret på `budget-service/pyproject.toml`:
  - `[project].dependencies`: fastapi, uvicorn[standard], pydantic, pydantic-settings,
    sqlalchemy[asyncio], asyncpg, psycopg2-binary, alembic, httpx, aio-pika, PyJWT[crypto],
    cryptography + `finans-tracker-{auth,contracts,messaging}`. **Ikke** `domain` (uimporteret),
    **ikke** `python-jose`, **ikke** `aiosqlite`.
  - `[tool.uv.sources]`: de tre shared-pakker som `path = "../shared/<navn>"`.
  - `[dependency-groups].dev`: ruff, mypy, pytest, pytest-asyncio, aiosqlite,
    `python-jose[cryptography]>=3.4.0`, `types-python-jose`, bandit.
  - `[tool.pytest.ini_options] asyncio_mode = "auto"`.
  - **Floors (`>=`), ikke exact pins (`==`).** `uv.lock` er hvad der pinner; `pyproject` erklærer
    kompatibilitet. Det er husets form i alle 10 og det er hele grunden til at lockfilen findes.
    Konsekvensen er at fastapi resolver til ~0.136 som budget — behandlet i **Risks**.
- `uv lock` → **ny** `uv.lock`. `uv sync --dev` for at bevise at sættet resolver lokalt.
- **Slet** `requirements.txt`.
- `makefile`: `install-deps` → `uv sync --dev`; alle targets → `uv run <cmd>`; `PYTHONPATH=`-
  præfikset fjernes fra de tre test-targets (contracts er nu en deklareret dep, ikke en sti);
  tilføj `dev`- og `migrate`-targets så filen matcher budgets. `typecheck` kommer i trin 4.
- Verificér: `make -C services/banking-service lint format-check test` — **grøn lokalt**, hvilket
  den aldrig har været (P3-39's banking-halvdel).

### 2. Dockerfile på `uv sync --frozen --no-dev` (commit 2)

- `services/banking-service/Dockerfile`, efter `budget-service/Dockerfile`s form:
  - `COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /usr/local/bin/`
  - `ENV` + **`PATH="/app/.venv/bin:$PATH"`**. Ikke-valgfrit: de fire workers overrider
    `command: ["python", "-m", ...]` i compose (`docker-compose.yml:723,739,757,779`). Uden
    PATH rammer de systeminterpreteren uden afhængigheder. Budgets Dockerfile bærer en
    kommentar om præcis dette — den kopieres med.
  - Tre `COPY services/shared/<navn> /shared/<navn>` — `/shared`, ikke under `/app`, fordi
    path-deps er `../shared/x` relativt til `/app/pyproject.toml`. Kun tre: ikke `domain`.
  - `COPY … pyproject.toml uv.lock ./` + `RUN uv sync --frozen --no-dev`.
  - `CMD` uændret.
- Behold `USER appuser` og `EXPOSE 8009` som de er.

### 3. Runtime-verifikation — trin 2's eneste egentlige bevis

`make check` er statisk og importerer ikke `app.main` under imagets versioner. Derfor:

- `docker compose build banking-service && docker compose up -d banking-service`
- `docker compose logs banking-service` — alembic kørt, uvicorn oppe under den *nye* fastapi.
- `curl localhost:8009/health` → 200.
- **Læs alle fire workeres logs**, ikke kun API'ets:
  `banking-outbox-worker`, `banking-account-projection-consumer`,
  `banking-saga-command-consumer`, `banking-sync-scheduler`. Hver skal have forbundet til
  RabbitMQ og ikke være i restart-loop. Det er her en manglende `PATH` viser sig, og kun her.
- `python3 scripts/compose_check.py` — skal blive ved at være grøn (regel 4 ser nu én fil, ikke
  to).

### 4. mypy-gaten (commit 3)

- `[tool.mypy]` i `pyproject.toml`: kopi af budgets blok — `packages = ["app"]`,
  `plugins = ["pydantic.mypy"]`, `disallow_untyped_defs`, `warn_unused_ignores`,
  `warn_redundant_casts`, `no_implicit_optional`, `[tool.pydantic-mypy] init_typed = true`.
- `typecheck: uv run mypy` i `makefile`; `check: lint format-check typecheck`.
- `uv run mypy` → ret fejlene. Enhver `# type: ignore` skal bære en item-reference.
- Tilføj `banking-service` til `TYPECHECK_SERVICES` (`ci.yml:145`). Det er hele indrulleringen,
  og at fjerne navnet igen er rollbacken.
- **Kontrol, ikke kun treatment:** verificér at gaten faktisk *kan* fejle for banking — indsæt
  en bevidst typefejl, se `uv run mypy` blive rød, fjern den igen. En grøn kørsel er den fejlmode
  vi har betalt for før (P3-40).

### 5. Docs (commit 4)

- `dev-notes/backlog/BACKLOG.md`: P3-23-rækken → `done 2026-07-28` + link hertil. P3-26's
  detail-sektion korrigeres: `python-jose`-halvdelen for banking er væk, `fastapi`-pinnet er
  blevet et floor. P3-39's banking-halvdel er også løst — rækken skal sige hvad der er tilbage
  (account).
- `dev-notes/STATUS.md`: Active/Next up, og **fire** "Standing traps"-formuleringer der bliver
  usande: pip-uden-venv, "banking's suite runs only in CI", "10 af 12", og "de 4 udenfor"
  bliver tre.
- `CLAUDE.md`: `TYPECHECK_SERVICES` er 9 af 12; "Undtagelserne er `account` og `banking`" →
  kun `account`; **og sætningen "Bemærk at banking dermed ikke er dækket af den gate dens egen
  bug motiverede" skal slettes** — det er hele pointen med dette item.
- Session-log i `dev-notes/sessions/`.
- `make notes-check` før commit. Bemærk at den verificerer mekanik, ikke sandhed.

## Risks & rollback

**fastapi 0.115.0 → ~0.136 er den reelle risiko.** Floors betyder at 21 versioner springes på
én gang. Den *kendte* fælde er ikke armeret (ingen `-> None`-ruter, verificeret), men
0.115→0.136 rummer mere end det. Detektion er trin 3: containeren op og fire workeres logs
læst. Hvis noget knækker er valget bevidst — jeg pinner `fastapi` snævert i `pyproject` og lægger
opgraderingen som eget item, frem for at blande en versions-migration ind i en install-sti-
ændring.

**Sekundær: `pydantic-settings` og `sqlalchemy` flytter også.** Samme detektion, samme udvej.

**Manglende `PATH` rammer kun workers.** API'et kan svare 200 mens alle fire consumers er døde,
og `docker compose ps` viser dem som kørende et stykke tid. Derfor er "læs workernes logs" et
eksplicit trin og ikke en note.

**Rollback** er per commit og billig: commit 4 er docs, commit 3 er ét navn i `ci.yml` plus en
mypy-blok, commit 2 er én fil, commit 1 genskaber `requirements.txt` fra git. Ingen migration,
ingen data, intet event-skema. `git revert` i omvendt rækkefølge er hele øvelsen.

**Accepteret omkostning:** account-service står tilbage som den ene service uden lockfile og
uden gate. Det gør "én install-sti per service" til en regel med én undtagelse frem for nul, og
CI's `elif [ -f requirements.txt ]`-gren skal blive stående til P3-01. Acceptabelt, fordi
alternativet er at koble dette item til en refactor der er flere gange større, og fordi banking
er den af de to der bærer både CVE'erne og den ubeskyttede fejlklasse.

## Outcome

Landet 2026-07-28 i fire commits. Alle fem færdig-kriterier holder, med én tilføjelse til
listen som planen ikke havde forudset (punkt 6 nedenfor).

| Kriterium | Resultat |
|---|---|
| `pyproject.toml` + `uv.lock`, `requirements.txt` væk | ✅ `6e9c8bda` |
| Image bygger + API og **fire** workers svarer | ✅ `6a998bc0`, verificeret to gange |
| `banking-service` i `TYPECHECK_SERVICES`, mypy grøn | ✅ `0fd25d59`, kontrol-verificeret i CI |
| `make test` / `lint` virker lokalt | ✅ 68 passed, første gang nogensinde |
| `python-jose` ude af runtime | ✅ dev-only på `>=3.4.0` |

**Versionsspring.** Floors valgt (bekræftet med brugeren). fastapi `0.115.0 → 0.140.7`,
sqlalchemy `2.0.36 → 2.0.51`, pydantic `2.9.0 → 2.13.4`. Ingen af dem knækkede noget: 68 tests
grønne, og imaget importerer `app.main` (6 ruter) plus alle fire worker-moduler. Planens
hovedrisiko udløste altså ikke — men det er *fordi* verifikationen var import-i-imaget og ikke
en grøn `make check`.

### Deviationer fra planen

1. **`tests/conftest.py` skulle ændres**, hvilket planen ikke havde forudset (den sagde kun at
   `app/` ikke røres). Filens `sys.path`-løkke indsatte `shared/{contracts,messaging,auth}` fra
   kildetræet, og dens docstring begrundede det eksplicit med at der ikke fandtes nogen
   `pyproject.toml` — en præmis dette item gjorde usand. At beholde den ville have givet pytest
   kildetræet og mypy den installerede kopi.
2. **Fem `app/`-filer blev rørt**, mod planens "ingen `app/`-fil røres for at ændre logik".
   Ingen logikændring: `@overload` på `_to_naive_utc`, en ny `sql_result.py` (kopieret fra
   budget/categorization), `__aexit__`-annotationer, og ignores. `rowcount(result)` erstatter
   `result.rowcount` på fire kaldsteder — samme runtime-værdi gennem en `cast`.
3. **`make check` inkluderede ikke `typecheck`** i mit første udkast af `makefile`; targetet stod
   i `.PHONY` uden at findes. Fanget ved at køre `make check` og se at mypy ikke var i output.
4. **P2-35 kostede to ignores, ikke én.** Se punkt 3 under "Hvad der gik anderledes".

### Hvad der gik anderledes end forventet

1. **Udbyttet var fire kendte items, ikke nye bugs.** 31 mypy-fejl fordelte sig som P2-32 (1),
   P2-33 (2), P2-35 (2), P2-36 (17 fejl på 3 linjer) + 5 ægte annotations-fejl. Præcis samme
   mønster som P2-31's egen udrulning. Ingen af de fire er rettet her, med vilje: at afgøre hvad
   et `str`-retry-header betyder er P2-36's beslutning, ikke en bivirkning af indrullering.
   Alle ni ignores bærer item-reference, og `warn_unused_ignores` gør dem selvoprydende.
2. **`python-jose` var kun brugt i én test.** Planens Context antog at den var en runtime-dep der
   *skulle* flytte gruppe; den var i virkeligheden aldrig en runtime-dep. Det gør P3-26's
   banking-halvdel helt lukket frem for udskudt.
3. **En kommentar jeg skrev var usand, og en trunkeret mypy-kørsel skjulte beviset.** Jeg
   begrundede P2-35-ignoren med at `update_status` og `update_consent` var uenige om deres egen
   nøgletype. Kørt uden `tail` fejlede `update_status` også — de er *enige*, begge kræver `UUID`.
   Kommentaren er rettet. Repoets `tail`-forbud handler om exit-koder; dette er samme fejlklasse
   for *læsning*.
4. **P3-39's `psycopg2`-begrundelse var forkert.** Rækken sagde at suiten kun nogensinde havde
   kørt i CI fordi `psycopg2` bygges fra kilde og fejler på macOS. Servicen har pinnet
   `psycopg2-binary` hele tiden; suiten kørte lokalt i første forsøg. Rækken er korrigeret.
5. **En præeksisterende ignore uden item-reference** lå i `sync_scheduler.py:89`; usynlig så længe
   mypy ikke kørte. Nu mærket P2-35.

### Open ends

- ~~CI har ikke kørt på dette.~~ **Lukket:** CI grøn på `e8865dcb` (run `30313411120`), og
  `make verify-typecheck-gate` rapporterer **9 gated / 3 not gated** med banking på `notice=no`
  — asymmetrien holder i begge retninger. Den lokale kontrol (bevidst typefejl → rød gate →
  fjernet) står stadig som den der beviste at gaten *kan* fejle for denne service.
- **`account` er nu ene tilbage** uden lockfile og uden mypy; CI's `elif [ -f requirements.txt ]`
  findes udelukkende for den (P3-01).
- **Ny deprecation, ikke filed:** fastapi 0.140.7's testclient advarer om at `httpx` med
  `starlette.testclient` er deprecated til fordel for `httpx2`. Rammer alle services på nyere
  fastapi — bør være ét tværgående item, ikke ét per service.

Fuld narrativ: [session-log](../sessions/2026-07-28-p323-banking-uv-pyproject.md).
