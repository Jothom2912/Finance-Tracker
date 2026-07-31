---
title: P3-59 — de fem tavse services får et spor, valgt efter én admissionsregel
date: 2026-07-31
status: done
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

2. [x] **`shared/auth`: én `logger.warning` på 401-stien** (`auth/fastapi.py:80-85`), der
   navngiver *hvorfor* fra `exc`. Version-bump på `finans-tracker-auth` + `uv.lock`-regen i
   hver forbruger. Test i pakkens egen suite med `caplog`, inkl. at de to *andre* 401-grene
   (manglende header, forkert format) **ikke** logger — de er entydige og falder uden for
   reglen.

3. [x] **user-service** — den billigste, fordi chokepunktet findes:
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

4. [x] **account-service** — flest punkter, ingen handlere i dag:
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

   ### Fase 4's resultat (2026-07-31)

   Otte kald, alle drevet fra en HTTP-request mod den kørende stak. **Planen var upræcis på
   ét punkt, og det punkt var dens egen vigtigste linje:**

   - Planen foreskrev at logge **non-200** i `user_adapter`. Efter reglen er det for meget:
     en `404` er user-services *entydige* "den bruger findes ikke", og det er præcis hvad
     400'en til klienten derefter siger. En linje dér ville fyre hver gang nogen taster et
     forkert bruger-id i en gruppe — netop den støj reglen findes for at holde ude. Cuttet
     er derfor `not in (200, 404)`. Det er samme afgørelse som fase 3's `UserNotFound`, set
     fra den anden ende af det samme kald.
   - Planens præmis om at 400'en også dækker "user-service er nede" **holder ikke helt**: er
     servicen helt væk, kaster `httpx` en `ConnectError` som ingen fanger → 500 med uvicorns
     egen traceback. Grimt, men ikke tavst. Det tvetydige tilfælde er non-404-*svar* — 401
     fra en roteret nøgle, 5xx fra en syg service — og det er dem linjen dækker.

   **Live-drevet, den stærkeste enkeltobservation i hele itemet.** Med en skæv
   `INTERNAL_API_KEY` (engangs-container, `docker compose run -e`) siger de to ender nu
   tilsammen hele diagnosen — fase 3 og fase 4 komponerer:

   ```
   user-service-1 | WARNING [app.adapters.inbound.rest_api] Internt bruger-opslag afvist: nøglen matcher ikke
   account-svc    | WARNING [app.adapters.outbound.user_adapter] user-service svarede 401 på eksistens-tjek
                    af bruger 497 — kaldet kollapser til 'findes ikke' og bliver en 400 til klienten
   account-svc    | WARNING [app.application.service] Kontooprettelse afvist: user-service kender ikke
                    bruger 497 fra et gyldigt token
   ```

   **Mutations-kontrollen viste hvorfor adapter-linjen ikke er valgfri.** Med den fjernet
   overlever `service.py`-linjen — og den *lyver*: "user-service kender ikke bruger 497" er
   falsk, brugeren findes, nøglen var skæv. En tavs log er dårlig; en log der selvsikkert
   siger det forkerte er værre. Mutationen blev verificeret i begge instrumenter: 0
   `user_adapter`-linjer i den live-drevne kørsel, og 4 røde tests — og kun de fire der hører
   til linjen.

   Live-tælling efter fase 4 (samme probe som step 1, plus tre nye drives):

   | drive | statuskode | linje |
   |---|---|---|
   | AC1 GET fremmed konto | 403 | `account_api` WARNING, med bruger, konto og ejer |
   | AC2 PUT fremmed konto | 403 | `account_api` WARNING, egen ordlyd (skriv ≠ læs) |
   | AC3 forkert intern nøgle | 403 | `internal_api` WARNING, uden nogen nøgleværdi |
   | AC4 intern nøgle mangler | 422 | **ingen** — uopnåelig gren, se nedenfor |
   | AC5 gruppe med ukendte id'er | 400 | `service` WARNING, navngiver `[987654, 987655]` |
   | AC6 gruppe med gyldige id'er | 201 | **ingen** (negativ kontrol) |
   | AC7 skæv nøgle → kontooprettelse | 400 | `user_adapter` + `service` WARNING |
   | ordinær 404 på `/accounts/999999` | 404 | **ingen** (negativ kontrol) |

   Step 1's `AC4`-fund er fastholdt som en test frem for kun en note: `Header(...)` er uden
   default, så "nøgle mangler helt" afvises af Pydantic med 422 og når aldrig
   `_verify_internal_key`. Giver nogen senere headeren en default, bliver testen rød i stedet
   for at grenen stille bliver nåelig.

   To bevidste fravalg, hver med en negativ test: den ordinære `404 "Konto ikke fundet"` og
   det interne `GET /{account_id}/owner`s 404 — sidstnævnte er både entydig *og* den normale
   måde goal-service får svaret på.

   **Dækningen her er svagere end i fase 3, og det er strukturelt.** `account` er ikke på
   typecheck-gaten (P3-01/P3-39: intet `pyproject.toml`) og har ingen lokal værktøjskæde, så
   tests, ruff og bandit blev kørt i en `python:3.11-slim`-container mod det mountede repo —
   samme sti som CI, men manuelt. 44 tests grønne, ruff og bandit rene.

5. [x] **goal-service** — fra nul til noget; `logger = logging.getLogger(__name__)` skal først
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

   ### Fase 5's resultat (2026-07-31)

   Fem HTTP-drevne linjer, alle fanget i `docker logs` mod den kørende stak. Instrumentet
   blev verificeret først med banking's `bank_api.py:145` (samme trigger som step 1), og
   den gav niveau, tidsstempel og `[app.…]`.

   | drive | statuskode | linje |
   |---|---|---|
   | G1 `GET /goals` fremmed `X-Account-ID` | 403 | `service` WARNING, navngiver **403** + bruger/konto/ejer |
   | G2 `X-Account-ID: abc` | 400 | `main` WARNING med værdien |
   | G2b `X-Account-ID` 300 tegn | 400 | `main` WARNING, afkortet til 64 |
   | G3 `GET /goals/50` fremmed mål | 404 | `service` WARNING, navngiver **404** + operation `læsning` |
   | G5 surplus, fremmed konto | 403 | `service` WARNING |
   | G4 ordinær 404 som ejer | 404 | **ingen** (negativ kontrol) |
   | G6 egen konto | 200 | **ingen** (negativ kontrol) |
   | upstream skæv nøgle → `GET`/`POST /goals` | 503 | `account_adapter` WARNING, navngiver 403'en |
   | upstream host væk → `GET`/`POST /goals` | 503 | `account_adapter` WARNING, `ConnectError` |

   403/404-asymmetrien er dermed **synlig i loggen med statuskoden på**, mens klienten ser
   præcis det samme som før. Det var hele pointen: 404-varianten var ikke til at skelne fra
   en helt almindelig "målet findes ikke".

   **Planen var upræcis på det sted den selv kaldte servicens værste, og live-kørslen
   afgjorde det.** Planen sagde: `account_adapter.exists`'s `except httpx.RequestError:
   return False` gør en nedetid til en 400 klienten aldrig genforsøger. Det sker ikke.
   `exists` har præcis én kalder — `service.py:94` i `create_goal` — og den kalder
   `_verify_ownership` **to linjer tidligere** (`:92`), altså `get_owner_user_id` mod samme
   upstream. Fejler upstream, rejses 503'en dér. Målt i begge fejlmoder (skæv
   `INTERNAL_API_KEY` via engangs-container; `ACCOUNT_SERVICE_URL` til en ikke-eksisterende
   host): `POST /goals` giver **503, ikke 400**, og `exists`-linjerne fyrede aldrig.

   Konsekvensen for tallet: `exists`'s to fejlgrene er **uopnåelige fra en request**. De er
   dækket af adapter-tests, men de tælles **ikke** som HTTP-drevne linjer — at gøre det
   ville være præcis den selvvalgte, flatterende optælling step 8 advarer imod
   (`feedback_baseline_can_be_accidentally_right`). Fundet er fastholdt som en
   reachability-test (`port.exists.assert_not_awaited()`) frem for en kommentar, af samme
   grund som fase 4's `AC4`: bytter nogen om på de to kald, bliver testen rød i stedet for
   at et dødt logkald bliver liggende og tælle med. Jf. `feedback_dead_suppression_annotations`
   — et logkald i en død gren har samme fejlform som en død `noqa`.

   Racen på default-mål-indexet (`main.py:127`) er det ene nye kald der **ikke** kan drives
   fra en enkelt request — den kræver to samtidige. Den er derfor dækket af en
   `TestClient`-test, og mutations-kontrolleret: fjernes linjen, bliver præcis én test rød.

   `X-Account-ID`-parsingen blev samlet i `_parse_account_id` fordi to ordret identiske
   `try/except`-kopier med tiden bliver to forskellige beskeder for samme afvisning.
   Værdien afkortes til 64 tegn: den er hele signalet, men den er også fremmed input, og en
   ubegrænset værdi ville lade en klient bestemme længden af vores loglinjer.

   121 tests grønne, ruff rent. **`goal` er ikke på typecheck-gaten** — planens step 7 var
   forkert om det; `TYPECHECK_SERVICES` i `ci.yml:158` har den ikke, og CLAUDE.md har ret
   (P2-34: `Goal` har to runtime-typer). Dækningen her er derfor som `account`s: tests +
   live-drift, ingen mypy.

6. [x] **notification + saga** — færrest punkter, mest tvetydige:
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

   ### Fase 6's resultat (2026-07-31)

   Syv HTTP-drevne linjer (4 notification, 3 saga), alle mod den kørende stak. Planen holdt
   her — begge services blev som beskrevet.

   **notification: én hjælper, tre tilstande, og en linje der siger at den ikke ved hvilken.**
   Alle tre blev fremprovokeret *live* frem for kun i tests, hvilket er hele grunden til at
   ordlyden er som den er:

   | drive | statuskode | linje |
   |---|---|---|
   | N1 `read` ukendt id | 404 | `main` WARNING |
   | N2 `dismiss` ukendt id | 404 | `main` WARNING, `afvisning` |
   | N3 `read` **fremmed** række (ejet af bruger 1) | 404 | `main` WARNING |
   | N4 `dismiss` egen række | 204 | **ingen** (negativ kontrol) |
   | N5 `dismiss` **igen** (allerede afvist) | 404 | `main` WARNING |
   | N6 `limit=0` | 422 | **ingen** (negativ kontrol) |
   | N7 `GET /notifications` | 200 | **ingen** (negativ kontrol) |

   N3 og N5 er de to der gør linjen værd at have: de er *ikke* til at skelne fra N1 —
   hverken for klienten eller i access-loggen — og de betyder noget helt andet.
   Testene kører mod en rigtig (sqlite-)DB frem for et fake repository, netop fordi
   påstanden er at de tre tilstande rammer *samme* gren; med en mock ville jeg kun teste min
   egen antagelse om hvad `WHERE`-klausulen gør.

   Asymmetrien mellem de to ruter blev bekræftet undervejs og er nu en negativ test:
   `mark_read` bruger `coalesce`, så et gen-mark **matcher** og logger intet (et dobbeltklik
   er normal brug), mens `dismiss`' `dismissed_at`-guard gør et gen-afvis til en 404 *med*
   linje. Havde begge logget, ville signalet drukne i dobbeltklik.

   **saga: én statuskode, tre årsager, tre ordlyd.** Alle tre drevet live — den korrupte
   gren krævede en ny probe-række (`22222222-…`, `context_json` med `user_id: ["1","2"]`)
   ud over step 1's `11111111-…`:

   | drive | statuskode | linje |
   |---|---|---|
   | S1 krydstenant (saga ejet af bruger 1) | 403 | `main` WARNING, navngiver bruger + ejer |
   | S2 intet `user_id` i konteksten | 403 | `main` WARNING, "utilgængelig for alle" |
   | S3 korrupt `user_id` (`['1', '2']`) | 403 | `main` WARNING **med værdien** |
   | S4 ukendt saga-id | 404 | **ingen** (negativ kontrol) |

   Værdien logges kun i S3, hvor den *er* diagnosen, og den kommer fra vores egen
   saga-kontekst — ikke fra requesten. Loggeren ligger i `main.py`, ikke i
   `postgres_saga_repository.py:15`s ubrugte logger: den fil importeres af alle fire workers,
   så en linje dér ville fyre i fem processer.

   **Mutations-kontrollen fandt en blind kontrol, og det er fasens mest lærerige del.**
   `test_the_three_branches_do_not_share_wording` sammenlignede oprindeligt `getMessage()`.
   Den er upræcis: to grene kan dele ordlyd og *stadig* give forskellige beskeder, fordi
   saga-id og bruger-id interpoleres ind — og krydstenant-grenen er den udsatte, da den er
   den eneste der kaldes med et andet bruger-id. Skiftet til `record.msg` (format-strengen)
   udtrykker den påstand jeg faktisk mener. Verificeret ved at kollapse den korrupte gren
   til den manglendes ordlyd: nu rød, hvor kollapset ellers kunne være sluppet igennem.
   Samme klasse som `project_measurement_instrument_validity` — en kontrol der ikke kan
   fejle på det den findes for at fange.

   Notifications mutation blev også kørt (fjern `dismiss`-kaldet): 2 røde tests, kun de to
   der hører til linjen.

   Begge services er på typecheck-gaten: mypy rent, ruff rent, 98 + 61 tests grønne.

7. [x] **Docs.** CLAUDE.md: ret `BankConnectionInactive`-eksemplet til `BankConfigError`, og
   ret `execute_with_logging`-konventionen til at sige hvad der faktisk findes (én service) —
   samme behandling som RHF+Zod-posten fik. `patterns/hexagonal-architecture.md:33-34, 47`
   samme. Plus backlog + STATUS.

8. [x] **Verification** (næste sektion).

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
7. `make check` + `make -C services/<svc> typecheck` for `user`, `notification` og `saga` —
   ~~`goal`~~ **er ikke på gaten**; det stod forkert her indtil fase 5 kørte, og
   `TYPECHECK_SERVICES` i `ci.yml:158` afgør det (CLAUDE.md havde ret: P2-34, `Goal` har to
   runtime-typer). **`account` er heller ikke** (P3-01/P3-39: intet `pyproject.toml`). For
   de to services udenfor er ændringerne kun dækket af punkt 2 og 6 — det er den svageste
   del af verifikationen og skal læses som sådan.
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

Reviewet og faserne fandt seks ting der ikke er logningshuller, og som en logningsplan ikke skal
afgøre. Alle seks er filet, så de ikke bor i en plan-fil alene:

1. **P2-43 — goal: en klient kan gøre en række permanent 500.** `dto.py:15` har `status: Optional[str]`
   uvalideret, `GoalResponse.status` er `GoalStatus` (`dto.py:38`), og `_to_dto`
   (`service.py:204`) bygger modellen direkte. `PUT /goals/{id}` med `{"status": "bogus"}`
   passerer 422, **committes**, og kaster derefter `ValidationError` → 500 ved hvert
   efterfølgende `GET` af det mål. Klient-trigget, persistent. Foreslås som **P2-tier** efter
   samme admissionsregel P1-13 brugte: klassen afgør tieren, ikke datoen.
2. **P3-60 — goal + account: upstream-nedetid rapporteres som en brugerfejl.** `account_adapter.py:24`
   og `user_adapter.py:26` giver 400 "findes ikke" når upstream er nede. Fase 4 og 5 gør det
   *synligt*; de retter ikke statuskoden til 503. Eget item — det er en kontraktændring.
3. **P3-61 — goal: `clear_default_savings_goal` mangler `deleted_at`-filteret**
   (`postgres_goal_repository.py:90-93`), hvor hver søsterstatement har det. Benignt i dag,
   men det er den inkonsistens der gør P3-16's invariant svær at stole på. Dertil: det
   partielle unique-index har ingen `deleted_at`-klausul, så invarianten holdes af konvention,
   ikke af skemaet.
4. **P3-62 — goal: `create_goal` gør to round-trips hvor den ene er død.** `service.py:92` kalder
   `_verify_ownership` → `get_owner_user_id`, som 404'er hvis kontoen ikke findes; `:94`
   kalder derefter `exists()` mod samme service. `exists()` kan kun returnere `False` hvis
   kontoen forsvandt mellem de to kald, og enhver upstream-fejl er allerede blevet en 503
   på det første. Altså: et ekstra HTTP-kald pr. målsoprettelse hvis eneste opnåelige
   resultat er `True`. Fundet under fase 5's live-kørsel. Fjernelsen er en adfærdsændring
   (`AccountNotFoundForGoal` ville skifte kilde), så den hører ikke i en logningsplan.
5. **P3-64 — `shared/auth`s 401-linje ligger uden for `app.*` og misses af platformens egen søgning.**
   Loggeren er `auth.fastapi`. Målt i efter-kørslen: `grep '\[app\.'` = 14 linjer,
   `grep WARNING` = 15. Den manglende er den ene linje der dækker alle ~10 services. Samme
   fejlform som `analytics.usecase`. Valget er ikke oplagt — `auth.*` er pakkens naturlige
   modulnavn — så det er en navngivnings-/gate-beslutning: skal delte pakker logge under
   `app.*`, eller skal en log-gate matche på niveau frem for loggernavn? Hører sammen med
   P3-11.
6. **P3-63 — goal: audit-trailet er bevaret i DB'en men uopnåeligt gennem API'et.**
   `get_allocation_history` kalder `get_by_id` først (`service.py:164`), som filtrerer
   `deleted_at IS NULL` → 404. P3-16 beholdt rækkerne netop for at bevare historikken.

## Outcome (2026-07-31)

**Alle fem services taler nu, og tallet er målt med samme probe som før-målingen.** Samme
script, samme 22 drives, samme instrument — det er hele grunden til at scriptet blev gemt i
step 1.

| service | `[app.*]`-linjer før | efter | udvalgte punkter (Y) | logget (X) |
|---|---|---|---|---|
| user | 0 | **4** | 8 | 8 |
| account | 0 | **3** | 8 | 7 (+1 uopnåelig: `AC4`) |
| goal | 0 | **3** | 7 | 5 (+2 uopnåelige: `exists`) |
| notification | 0 | **2** | 6 | 6 |
| saga | 0 | **2** | 4 | 4 |

De to tal er forskellige med vilje. **Efter-linjerne** er hvad *denne probe* driver i én
kørsel; **X af Y** er alle de punkter admissionsreglen udvalgte, inkl. dem der kræver en
skæv nøgle, en død upstream eller to samtidige requests og derfor ikke ligger i probens 22
drives. Y er de udvalgte punkter — **ikke** de 96. Et "0 → N" på et selvvalgt Y er
tilfældigt flatterende, og det er sket før
(`feedback_baseline_can_be_accidentally_right`), så begge tal står her frem for det
pænere ene.

Verifikationens punkter, i den rækkefølge de blev kørt:

1. **Instrumentet:** banking's `bank_api.py:145` gav niveau, tidsstempel og `[app.…]`. Ikke
   gateway'ens `auth.py:113` som planen sagde — den fyrer ikke, hvilket P3-57 allerede havde
   dokumenteret. Se step 1.
2. **5/5 services** har mindst én HTTP-drevet warning. Kriteriet er nået.
3. **Negativ kontrol:** ordinær 404 (`/goals/999999` som ejer), 422 fra Pydantic
   (`limit=0`, og `AC4`s manglende header) → **nul** nye linjer. Access-linjen står alene.
4. **Negativ kontrol på `shared/auth`:** manglende `Authorization` og malformet `Bearer`
   logger ikke; kun den udekodbare token gør. 1 af 3 401-grene, som besluttet.
5. **Mutations-kontrol:** kørt tre gange — `user_adapter` (fase 4), default-mål-racen (fase
   5) og notifications `dismiss`-kald + sagas wording-test (fase 6). Hver gang blev præcis de
   tests røde der hører til linjen.
6. **`caplog`-tests** for hvert nyt kald: niveau, loggernavn, diskriminerende værdi, plus en
   negativ test pr. fravalg.
7. `make check` + `mypy` grønt på `user`, `notification`, `saga`. `goal` og `account` er
   **ikke** på gaten, så deres dækning er tests + live-drift. Det er verifikationens
   svageste del og skal læses som sådan.

### Det itemet lærte, ud over linjerne

**(1) Reglen var det egentlige produkt, og den holdt hele vejen — men den var upræcis to
gange, og begge gange på planens *vigtigste* linje.** Fase 4: `user_adapter` skulle logge
non-200, men en 404 er user-services entydige svar, så cuttet blev `not in (200, 404)`. Fase
5: `exists`'s fejlgrene kan slet ikke nås fra en request. Begge fund kom fra at *drive*
koden, ikke fra at læse den. En regel skrevet før koden er stadig en hypotese.

**(2) Et logkald i en uopnåelig gren er samme fejlform som en død `noqa`.** Tre af planens
kald ligger i grene der ikke kan nås (`AC4`s 422-afvisning, `exists`' to). De er beholdt —
de er korrekte hvis de nås — men de er **fastholdt med reachability-tests** frem for
kommentarer, og de tælles ikke som HTTP-drevne. Jf.
`feedback_dead_suppression_annotations`.

**(3) En kontrol kan selv være blind, og fase 6 fangede en.** Sagas
wording-test sammenlignede `getMessage()`, hvor to grene kan dele ordlyd og *alligevel* give
forskellige beskeder fordi id'erne interpoleres ind. Nu `record.msg`, mutations-verificeret
ved et ægte kollaps. `project_measurement_instrument_validity`, instans nummer otte.

**(4) Den mest værdifulde linje i itemet er usynlig for platformens egen søgning.**
`shared/auth`s 401-warning logger på **`auth.fastapi`**, ikke `app.*`. Målt i efter-kørslen:
`grep '\[app\.'` finder 14 linjer, `grep WARNING` finder 15 — den manglende er præcis den
linje der dækker alle ~10 services. Det er samme fejlform som `execute_with_logging`s
`analytics.usecase`, som fase 7 lige skrev ned i CLAUDE.md. En log-gate scopet til `app.*`
ville være grøn uden at se den. **Spawnet som eget item** (nedenfor) — det er en
navngivnings-/gate-beslutning, ikke en logningsmangel.

**(5) To ender af samme kald komponerer, og mutationen viste hvorfor det ikke er valgfrit.**
Fase 3 + fase 4 giver tilsammen hele diagnosen ved en roteret nøgle. Fjern
adapter-linjen, og `service.py`-linjen overlever og *lyver*: "user-service kender ikke
bruger 497" er falsk. En tavs log er dårlig; en log der selvsikkert siger det forkerte er
værre. Det er den observation der bedst forsvarer hele itemet.
