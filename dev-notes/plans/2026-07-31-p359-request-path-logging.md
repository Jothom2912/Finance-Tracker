---
title: P3-59 — de fem tavse services får et spor, valgt efter én admissionsregel
date: 2026-07-31
status: open
backlog-items: [P3-59]
related:
  - plans/2026-07-31-p357-api-logging-config.md
  - findings/2026-07-31-account-service-log-silenced-by-alembic.md
  - decisions/2026-07-29-taxonomy-authorization.md
---

# P3-59 — de fem tavse services får et spor, valgt efter én admissionsregel

## Goal

`account`, `user`, `goal`, `notification` og `saga` kan i dag ikke sige noget om sig selv når
en request går skævt: **0 af 96 afvisnings- og fejlpunkter i de fem API-processers request-sti
efterlader en loglinje** (målt, tabel i [Context](#context)). P3-57 gav dem en konfiguration;
denne plan giver dem noget at konfigurere *for*.

Færdig når:

1. Hver af de fem services producerer mindst én `logger.warning`/`error` der kan **drives fra
   en HTTP-request** mod den kørende stak — altså samme slags trigger de øvrige syv har i
   P3-57's tabel, så en log-baseret verifikation af platformen ikke længere har fem huller.
2. Hvert nyt kald er valgt af den admissionsregel i [Beslutninger](#beslutninger-før-kode), ikke
   af "her manglede der noget" — og de afvisninger reglen *afviser* er skrevet ned som
   fravalg, ikke overset.
3. En **negativ kontrol** består: en ordinær 404 og en 422 producerer stadig ingen linje ud
   over uvicorns access-linje. Ellers har vi bygget en anden access-log oven på den vi lige
   fik.
4. En **mutations-kontrol** består: fjern et af de nye kald, og verifikationen bliver rød.

## Context

P3-57's [Step 1 (ii)](2026-07-31-p357-api-logging-config.md#ii-5-af-12-har-ingen-reachable-warning-at-måle-på--heller-ikke-efter-fixet)
fandt at fem af de tolv API-processer ikke havde en reachable warning at måle på — heller ikke
efter fixet. Det blev filet som P3-59 frem for scope-creep, og backloggen formulerede det som
**et review, ikke et fix**: *hvilke afvisninger og domænefejl burde efterlade et spor, og på
hvilket niveau*. Reviewet er kørt (fire parallelle gennemgange af inbound-adaptere,
application- og domain-lag pr. service, worker-moduler ekskluderet). Resultatet:

| service | afvisnings-/fejlpunkter i request-stien | loggede | logger deklareret men ubrugt |
|---|---|---|---|
| account | 45 | **0** (den ene ERROR ligger i lifespan-migrationen) | `application/service.py:37` |
| user | 38 | **0** (tre `logger.info` på success-stien) | `main.py:21` — i filen med alle fire exception-handlers |
| goal | ~30 | **0** — nul logging-statements i hele API-processen | — |
| notification | 7 | **0** — alle fire warnings ligger i consumer-processen | — |
| saga | 8 | **0** — alle tre warnings ligger i orchestratoren | `adapters/outbound/postgres_saga_repository.py:15` |

**Tre af de fem deklarerer allerede en logger de aldrig bruger**, så diffen er mindre end tallene
antyder. `user-service` er det skarpeste tilfælde: `main.py:21` opretter en logger, og de fire
`@app.exception_handler`-funktioner umiddelbart nedenunder — det chokepunkt hver enkelt
domæneafvisning i servicen passerer — logger intet.

**Det reviewet ændrede ved min forventning:** jeg gik ind i det for at finde "manglende
warnings" og fandt at det interessante ikke er *at* der mangler linjer, men at en stor del af de
96 punkter **ikke bør have en linje**. Efter P3-57 bærer hver request allerede en access-linje
med metode, sti og statuskode. Et `logger.warning("Konto ikke fundet")` ved siden af en
`404`-access-linje tilføjer nul information. Det gav admissionsreglen nedenfor, og reglen er
det egentlige produkt af dette item — den er grunden til at planen tilføjer ~20 kald og ikke ~96.

## Beslutninger før kode

### Admissionsreglen

> **En afvisning fortjener en loglinje, hvis og kun hvis statuskoden alene er tvetydig om
> årsagen.**

Access-linjen siger *hvad* der skete. Den kan ikke sige *hvorfor*, og det er præcis dér de fem
services er tavse på en måde der koster noget:

- En `403` fra `account_api.py:47` kan være et krydsbruger-forsøg — eller en helt normal bruger
  med en forældet konto-id i frontenden. Access-linjen skelner ikke.
- En `400 "Bruger med dette ID findes ikke"` fra account kan betyde at brugeren ikke findes —
  **eller at `user-service` er nede, eller at `INTERNAL_API_KEY` er roteret**
  (`user_adapter.py:26`: `return response.status_code == 200`). Det er en konfigurationsfejl
  rapporteret til slutbrugeren som en valideringsfejl, i tavshed, i begge ender.
- En `403 "Access denied"` fra `saga-service/app/main.py:54` har **tre** årsager: sagaen har
  intet `user_id` i sin kontekst, konteksten er korrupt (`except (TypeError, ValueError):
  owner_id = None`, `:50-53`), eller det er et ægte krydstenant-forsøg. Den første og anden er
  data-integritetssignaler; den tredje er et sikkerhedssignal. Samme respons, samme tavshed.

Reglen har en pris vi accepterer eksplicit: **den logger ikke det normale.** En ordinær 404 på
et mål der ikke findes, og enhver 422 fra Pydantic, får ingen linje. Hvis vi senere vil kunne
tælle 4xx pr. rute, er svaret access-logs eller `/metrics` (P3-11) — ikke 96 `logger.warning`.

### Niveauer, afledt af hvad der allerede står i repoet

Ikke opfundet her; læst af banking `main.py:53-99` og analytics `main.py:54-58`:

| niveau | betyder | eksempel i denne plan |
|---|---|---|
| `warning` | forventet, men siger noget om en **caller** eller en **upstream** | krydsbruger-403, upstream nede, absorberet race, afvist intern nøgle |
| `error` / `exception` | uventet — **vores** fejl, med stacktrace | uhåndteret `IntegrityError`, malformet upstream-payload |
| `info` | gennemført tilstandsændring | user-services tre eksisterende — udvides ikke |

`%`-style lazy args, aldrig f-strings; `exc_info` kun på `error`/`exception`. Det er den idiom
alle fire referencesites i P3-57's tabel bruger.

### Åbne valg

**(1) `services/shared/auth`s 401 — den største enkeltgevinst, og den ligger uden for de fem.**

`services/shared/auth/auth/fastapi.py:80-85` fanger `InvalidTokenError`, kaster en generisk 401
og **smider `exc` væk**. `exc` er det eneste sted der findes hvorfor: udløbet vs. forkert
signatur vs. manglende `user_id`-claim. Ét `logger.warning` dér instrumenterer mislykket
autentifikation i **alle ~10 services der bruger pakken**, inklusive de fem.

Trade-off: det udvider scope fra fem services til pakken, kræver version-bump + `uv.lock`-regen
i hver forbruger (path-deps installeres som kopier — samme mekanik som `py.typed`-reglen i
CLAUDE.md), og har en volumen-risiko: en frontend i et token-refresh-loop kan spamme loggen.

**Anbefaling: med, som sit eget commit** — dels fordi den løser mest pr. linje, dels fordi den
er den eneste ændring her der også gør de *syv andre* services bedre. Volumen-risikoen tages
ved at logge på `warning` uden `exc_info` og med tokenets `sub`/`user_id` udeladt (vi har det
ikke — tokenet kunne ikke dekodes).

**(2) Skal `execute_with_logging` promoveres til `shared/observability`?**

CLAUDE.md kalder den en konvention ("`execute_with_logging` wrapper på use cases"). **Den findes
i én service.** Definitionen ligger i `analytics-service/app/shared/logging.py:17`, er bundet
til `AnalyticsDomainError`, og bruger loggernavnet `"analytics.usecase"` — altså uden for
`app.*`, så et `grep '\[app\.'` misser hver linje den udsender.

- (a) **Promovér**, parameteriseret på domænets base-exception. Giver de fem konsistent
  use-case-logging med varighed.
- (b) **Lad den ligge**, og log i stedet på exception-handlerne.

**Anbefaling: (b).** (a) udsender en `info`-linje pr. use case med `outcome=ok` — som er
netop det access-linjen allerede siger, altså det admissionsreglen afviser. Varigheden er et
*telemetri*-deliverable (P3-11), ikke et observability-hul, og at afgøre den som bivirkning her
ville binde os til en wrapper vi ikke har målt behovet for. Exception-handleren er desuden det
præcise chokepunkt: user-services fire handlere dækker alle servicens 401/403/404/409.

**(3) Skal `patterns/hexagonal-architecture.md` og CLAUDE.md rettes i samme plan?**

Under reviewet faldt to dokumenterede konventioner: CLAUDE.md's eksempel
`BankConnectionInactive → 503 + WARNING log` er **usandt** — den er 409 uden log, både i
`banking/app/main.py:48` og `bank_api.py:237`. De ægte 503+WARNING-eksemplarer er
`BankConfigError` (`banking/app/main.py:94-99`) og `ReadStoreUnavailableError`
(`analytics/app/main.py:54-58`). Plus (2) ovenfor.

**Anbefaling: ja, som sidste commit.** Det er samme fejlform som RHF+Zod-posten i CLAUDE.md, og
den post er allerede præcedens for at en konvention der beskriver kode som ikke findes er værre
end ingen: den får en review til at efterspørge det forkerte. Vi retter *eksemplet*, ikke
konventionen.

## Non-goals

- **Ingen adfærdsændringer i afvisningerne.** Statuskoder, bodies og beskeder står. Vi
  tilføjer et spor, vi omdefinerer ikke kontrakten. To steder gør det ondt og gøres alligevel
  ikke her, se [spawnede items](#items-der-spawnes-ikke-løses-her).
- **Ingen linje på 422 og ingen på ordinær, entydig 404.** Direkte konsekvens af
  admissionsreglen. Skrevet som fravalg, så en senere review ikke læser det som en forglemmelse.
- **Ingen strukturering/JSON, ingen request-id.** Uændret fra P3-57's non-goals; request-id
  kræver middleware + contextvars i 12 services og er sit eget item.
- **Ingen migration af de 23 `setup_worker_logging`-kaldsteder.** Uændret fra P3-57.
- **Ingen ændring af de syv services der allerede har en reachable warning.** Undtagelsen er
  `shared/auth` (åbent valg 1), som rammer dem alle — og det er navngivet som en scope-udvidelse,
  ikke smuglet ind.
- **Ingen `LOG_LEVEL`-ændring.** Alle nye kald er `warning`/`error` og er derfor synlige på
  den `INFO`-default P3-57 satte.

## Steps

Commits følger `feedback_commit_per_fase`: én commit per fase, så en rollback kan ramme
præcist — og fase 2 kan rulles tilbage alene, hvilket er hele grunden til at den er sin egen.

1. [x] **Før-måling i den kørende stak, gemt.** Ingen kodeændring. For hver af de fem: driv de
   afvisninger admissionsreglen udvælger, og gem `docker logs` for hver. Forventning: nul
   linjer. **Verificér instrumentet først** ved at drive gateway'ens kendte
   `auth.py:113`-warning og se den — en tom log fra et blindt instrument er ikke et resultat
   (`project_measurement_instrument_validity`). Skriv tallene ind her som `Step 1's resultat`.

   ### Step 1's resultat (2026-07-31)

   **Instrumentet blev verificeret med en anden trigger end planen foreskrev.** Planen sagde
   gateway'ens `auth.py:113` — men P3-57's egen outcome havde allerede dokumenteret at netop
   den ikke fyrer, fordi probe-brugeren *har* en `Default Account`. At følge planen her ville
   have gjort instrument-checket til den fejl den findes for at fange. Brugt i stedet:
   banking's `bank_api.py:145` (`GET /api/v1/bank/callback?state=p359probe`, ingen auth), som
   P3-57 verificerede. Den gav:

   ```
   banking-service-1 | 2026-07-31 00:39:03,617 WARNING  [app.adapters.inbound.bank_api] \
     Bank callback missing authorization code [f558978a]: state=p359probe
   ```

   Niveau, tidsstempel og logger-navn er der — instrumentet ser app-linjer.

   Probe-scriptet driver 22 afvisninger (gemt, så efter-målingen bruger samme instrument).
   Alle 22 rammer den forventede statuskode. Log-tællingen bagefter:

   | service | `[app.*]`-linjer | WARNING/ERROR | access-linjer |
   |---|---|---|---|
   | user | **0** | 0 | 14 |
   | account | **0** | 0 | 15 |
   | goal | **0** | 0 | 16 |
   | notification | **0** | 0 | 12 |
   | saga | **0** | 0 | 11 |

   **Access-linjerne er kontrollen der gør nullerne til et resultat:** requesten *nåede* hver
   service og blev afvist, og servicen sagde alligevel intet om hvorfor. Havde access-tallet
   også været 0, ville nullerne kun have betydt at proben ikke ramte.

   Tre fund proben tilføjede til reviewets billede:

   - **`G3` bekræfter 403/404-asymmetrien empirisk**: `GET /goals` med fremmed `X-Account-ID`
     giver 403, `GET /goals/50` på et fremmed mål giver 404. Samme krydsbruger-forsøg, to
     statuskoder — linjen i fase 5 skal derfor sige *hvilken* af de to der skete.
   - **`AC4` (intern nøgle helt udeladt) giver 422, ikke 403**, fordi `internal_api.py:17`
     bruger `Header(...)` uden default. Pydantic afviser før `_verify_internal_key` kører, så
     den gren er *uopnåelig* fra "ingen header" — kun "forkert header" rammer den. Det ændrer
     fase 4's formulering: 403-linjen dækker forkert nøgle og ikke-konfigureret nøgle, ikke
     manglende header.
   - **Saga havde ingen instans for probe-brugerne** (registrering er event-drevet, ikke en
     saga), så krydstenant-403'en drives mod en saga ejet af `user_id=1`. Den korrupte
     context-gren krævede en indsat probe-række (`11111111-…-111111111111`, `context_json`
     uden `user_id`) — begge saga-årsager er altså drivbare, men kun den ene uden DB-setup.

2. [ ] **`shared/auth`: én `logger.warning` på 401-stien** (`auth/fastapi.py:80-85`), der
   navngiver *hvorfor* fra `exc`. Version-bump på `finans-tracker-auth` + `uv.lock`-regen i
   hver forbruger. Test i pakkens egen suite med `caplog`, inkl. at de to *andre* 401-grene
   (manglende header, forkert format) **ikke** logger — de er entydige og falder uden for
   reglen.

3. [ ] **user-service** — den billigste, fordi chokepunktet findes:
   - `main.py:32-52`: log i de fire handlere. `InvalidCredentialsException` → `warning`
     (mislykket login er i dag **helt uden spor**, så credential-stuffing er usynligt);
     `CurrentPasswordIncorrectException` → `warning`; `UserAlreadyExistsException` og
     `UserNotFoundException` → vurderes mod reglen, se note nedenfor.
   - `application/service.py:70-80` og `:189-194`: de to kasserede `IntegrityError` →
     `warning` med originalen. En race er i dag umulig at skelne fra en almindelig
     dobbelt-tilmelding.
   - `postgres_user_repository.py:80-83`: `rowcount == 0` (TOCTOU, kommentaren beskriver den
     allerede) → `warning`.
   - `rest_api.py:27` (503, `INTERNAL_API_KEY` ikke sat) og `:32` (401, nøglen matcher ikke) →
     `warning`. Det er den ene ende af det tavse account→user-kald.

   Note til reglen: `UserNotFoundException` fra `GET /me` med et *gyldigt* token er tvetydig
   (bruger slettet under en levende session) og fortjener en linje; fra det interne
   `GET /{user_id}` er den entydig. Samme exception, to tvetydigheder — så linjen hører i
   handleren, med ruten på.

4. [ ] **account-service** — flest punkter, ingen handlere i dag:
   - `account_api.py:47` og `:90`: de to ejerskabs-403'er → `warning`. Et krydsbruger-forsøg,
     læs som skriv, er i dag sporløst.
   - `user_adapter.py:26` og `:32-42`: non-200 fra user-service → `warning` **før** det
     kollapser til `False`. Det er planens vigtigste enkeltlinje: uden den er "user-service er
     nede" og "brugeren findes ikke" den samme 400.
   - `internal_api.py:21`: 403 på intern nøgle → `warning`, og linjen skal skelne
     *nøgle-ikke-konfigureret* fra *nøgle-forkert* — betingelsen `not INTERNAL_API_KEY or
     x_internal_api_key != INTERNAL_API_KEY` blander dem i dag.
   - `application/service.py:73`, `:165`, `:188`: de tre domænefejl loggede ved raise, så den
     ubrugte logger på `:37` får sit formål.

5. [ ] **goal-service** — fra nul til noget; `logger = logging.getLogger(__name__)` skal først
   oprettes:
   - `account_adapter.py:24-25`: `except httpx.RequestError: return False` → `warning`. Det
     er servicens værste sted: en nedetid bliver en 400 klienten (korrekt) aldrig genforsøger.
   - `main.py:104-107`: `IntegrityError` → 409 på det partielle unique-index → `warning`. I
     dag er der ingen måde at vide om racen fyrer én gang om måneden eller konstant.
   - `main.py:53` og `:67`: `except ValueError` på `X-Account-ID` → `warning` (plausibelt
     probe-signal).
   - `service.py:26` (`NotAccountOwner` → 403) plus de seks `return None`-ejerskabsstier
     (`service.py:35, 84, 118, 137, 152, 167`): **én** `warning` på det sted der kan skelne
     "findes ikke" fra "ikke din". Bemærk asymmetrien reviewet fandt: `GET /goals` med en
     fremmed `X-Account-ID` giver 403, `GET /goals/{id}` giver 404 — ikke forkert, men
     uensartet, og linjen skal derfor sige hvilken af de to der skete.

6. [ ] **notification + saga** — færrest punkter, mest tvetydige:
   - notification `main.py:65` og `:78`: 404 hvor ejerskabstjekket ligger i `WHERE`-klausulen
     (`postgres_notification_repository.py:100-108`, `:128-136`), så "findes ikke", "ikke din"
     og "allerede afvist" er samme svar. At skelne dem koster en ekstra query, og det er
     **ikke** værd at betale: log tvetydigheden ærligt i stedet ("no row matched for user=%s
     id=%s — not found, not owned, or already dismissed"). En linje der lyver om hvor præcis
     den er, er værre end en der ikke ved det.
   - saga `main.py:50-53`: den korrupte `context["user_id"]` → `warning` **med** værdien.
     Det er et data-integritetssignal, ikke et auth-signal, og det er i dag umuligt at skelne
     fra et probe.
   - saga `main.py:54`: 403 → `warning`, og den skal navngive hvilken af de tre årsager der
     ramte. `postgres_saga_repository.py:15`s ubrugte logger er ikke det rigtige sted — den
     fil importeres af **alle fire workers** også, så en linje dér fyrer i fem processer.

7. [ ] **Docs.** CLAUDE.md: ret `BankConnectionInactive`-eksemplet til `BankConfigError`, og
   ret `execute_with_logging`-konventionen til at sige hvad der faktisk findes (én service) —
   samme behandling som RHF+Zod-posten fik. `patterns/hexagonal-architecture.md:33-34, 47`
   samme. Plus backlog + STATUS.

8. [ ] **Verification** (næste sektion).

## Verification

Rækkefølgen er valgt så et fladt resultat kan afvises som instrumentfejl før det tros.

1. **Instrumentet, først.** Driv gateway'ens `auth.py:113`-warning og se linjen med niveau,
   tidsstempel og `[app.…]`. Består den ikke, er intet andet tal i denne sektion et resultat.
2. **Adfærdsmæssigt, pr. service.** For hver af de fem: send den request der udløser hvert nyt
   kald mod den kørende stak, og fang linjen i `docker logs`. **Ikke** `grep -c logger.warning`
   i kilden — det er det blinde instrument her: det tæller kald der findes, ikke kald der
   fyrer. Kriteriet er 5/5 services med mindst én HTTP-drevet warning.
3. **Negativ kontrol.** En ordinær 404 (`GET /api/v1/goals/999999` som ejer) og en 422
   (`limit=0` på notification) må give **nul** nye linjer ud over access-linjen. Fejler den,
   har vi bygget en anden access-log.
4. **Negativ kontrol på `shared/auth`.** Manglende `Authorization` og malformet `Bearer`-header
   må ikke logge — kun den udekodbare token gør.
5. **Mutations-kontrol.** Fjern `user_adapter.py`s nye linje og kør punkt 2 igen: account skal
   blive rød. Fejlmoden vi vogter er en grøn kørsel der intet beviste
   (`project_per_worker_image_staleness`), og den fanges kun af en kontrol, ikke af en treatment.
6. **`caplog`-tests** for hvert nyt kald: niveau, loggernavn og at beskeden indeholder den
   diskriminerende værdi. En loglinje med forkert logger eller niveau er præcis den tavse fejl
   dette item findes for.
7. `make check` + `make -C services/<svc> typecheck` for `user`, `notification`, `saga`, `goal`
   (alle fire er på gaten). **`account` er ikke** (P3-01/P3-39: intet `pyproject.toml`), så
   dens ændringer er kun dækket af punkt 2 og 6 — det er den svageste del af verifikationen og
   skal læses som sådan.
8. Efter-tallet skrives som `X af Y punkter logget, pr. service`, med Y = de punkter reglen
   udvalgte — ikke de 96. Et "0 → N" på et selvvalgt Y er tilfældigt flatterende, og det er
   sket før (`feedback_baseline_can_be_accidentally_right`).

## Risks & rollback

| risiko | detektion | rollback |
|---|---|---|
| `shared/auth`-bumpet regenererer 10 lockfiles og en service starter ikke | start containeren og læs **workernes** logs, ikke kun API'ets (CLAUDE.md: `make check` er statisk og importerer ikke `app.main`) | revert fase 2 alene — derfor er den sit eget commit |
| 401-linjen spammer loggen fra et token-refresh-loop i frontenden | mål linjer/minut i punkt 2's kørsel med frontenden åben | flyt til `info`, eller drop fase 2 |
| En ny linje lækker et hemmeligt materiale | review: intet kald må logge tokens, password-felter eller nøgleværdier — `internal_api.py` logger *at* nøglen ikke matchede, aldrig hvad der blev sendt | revert den enkelte linje |
| Vi tilføjer en linje der duplikerer access-linjen | verifikationens punkt 3 | fjern linjen; reglen har afgjort det |
| Fem services × ~20 kald bliver "logging for logningens skyld" | reglen er skrevet ned *før* koden, og hvert kald skal kunne begrundes med den tvetydighed det opløser | — |

## Items der spawnes, ikke løses her

Reviewet fandt fire ting der ikke er logningshuller, og som en logningsplan ikke skal afgøre:

1. **goal: en klient kan gøre en række permanent 500.** `dto.py:15` har `status: Optional[str]`
   uvalideret, `GoalResponse.status` er `GoalStatus` (`dto.py:38`), og `_to_dto`
   (`service.py:204`) bygger modellen direkte. `PUT /goals/{id}` med `{"status": "bogus"}`
   passerer 422, **committes**, og kaster derefter `ValidationError` → 500 ved hvert
   efterfølgende `GET` af det mål. Klient-trigget, persistent. Foreslås som **P2-tier** efter
   samme admissionsregel P1-13 brugte: klassen afgør tieren, ikke datoen.
2. **goal + account: upstream-nedetid rapporteres som en brugerfejl.** `account_adapter.py:24`
   og `user_adapter.py:26` giver 400 "findes ikke" når upstream er nede. Fase 4 og 5 gør det
   *synligt*; de retter ikke statuskoden til 503. Eget item — det er en kontraktændring.
3. **goal: `clear_default_savings_goal` mangler `deleted_at`-filteret**
   (`postgres_goal_repository.py:90-93`), hvor hver søsterstatement har det. Benignt i dag,
   men det er den inkonsistens der gør P3-16's invariant svær at stole på. Dertil: det
   partielle unique-index har ingen `deleted_at`-klausul, så invarianten holdes af konvention,
   ikke af skemaet.
4. **goal: audit-trailet er bevaret i DB'en men uopnåeligt gennem API'et.**
   `get_allocation_history` kalder `get_by_id` først (`service.py:164`), som filtrerer
   `deleted_at IS NULL` → 404. P3-16 beholdt rækkerne netop for at bevare historikken.

## Outcome (udfyldes når den er kørt)
