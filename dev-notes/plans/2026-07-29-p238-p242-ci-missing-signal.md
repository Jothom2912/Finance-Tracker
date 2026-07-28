---
title: P2-38 + P2-42 — CI's manglende signal: jobtimeouts, ES-fixturens wait-timeout, døde workers og bankings 500→503
date: 2026-07-29
status: done
backlog-items: [P2-38, P2-42]
related:
  - ../findings/2026-07-28-ci-job-can-hang-undetected.md
  - ../findings/2026-07-28-banking-service-dead-in-ci.md
  - ../findings/2026-07-25-banking-ci-could-not-collect.md
  - ../plans/2026-07-28-p239-browser-automation.md
---

# P2-38 + P2-42 — CI's manglende signal

## Goal

CI skal kunne **rapportere** to fejltilstande den i dag er tavs om: et job der hænger, og en
container der er død. Færdig når (a) hvert job i `ci.yml` har en `timeout-minutes` sat efter
målt varighed, (b) `es_container`-fixturen fejler med en læsbar pytest-fejl frem for at hænge,
(c) `e2e-tests` fejler hvis en compose-container er exited nonzero eller i restart-loop, og
(d) banking svarer **503 + WARNING** frem for 500 når integrationen ikke er konfigureret.

Hvert af de fire delfix skal være **verificeret rødt** på den tilstand det findes for — ellers
er det endnu en grøn gate der intet beviser, som er præcis den fejlklasse itemet lukker.

## Context

De to items er samme fejlmode fra hver sin ende. P2-38 er "jobbet slutter aldrig"
([finding](../findings/2026-07-28-ci-job-can-hang-undetected.md): analytics' `Run tests` sad
836 s hvor baselinen er 36 s, og ville have siddet i 360 min). P2-42 er "servicen startede
aldrig" — [banking var død i CI](../findings/2026-07-28-banking-service-dead-in-ci.md) så længe
`e2e-tests` havde kørt, og blev først fundet af P2-39's browser-suite, ikke af CI.
Klassen er den samme som [banking's CI-job der ikke kunne collecte](../findings/2026-07-25-banking-ci-could-not-collect.md):
**en gate der ikke kan rapportere fejl.**

**To tal i backloggen er forkerte, og det ændrer scopet.** Målt i dag:

1. **`grep -c timeout-minutes .github/workflows/ci.yml` giver 1, ikke 0.** P2-39 satte
   `timeout-minutes: 30` på `e2e-tests` (`ci.yml:290`) med P2-38 navngivet i kommentaren.
   Tilbage er de fire øvrige job-definitioner: `repo-lint`, `python-services` (matrix),
   `shared-packages`, `frontend`. Det hængte job var analytics under `python-services` —
   altså stadig udækket, men scopet er fire jobs, ikke fem.

2. **"9 af 53 compose-services har en opstarts-gate" er den forkerte nævner.** De 53 fordeler
   sig: **14** datastores/infra (har allerede compose-`healthcheck` + `depends_on:
   service_healthy`), **12** HTTP-services, **1** frontend/nginx, **26** workers.
   `Wait for system` poller 9 porte + 3000, så af de 12 HTTP-services er **9 gated** og **3
   ikke**: ai (8007), notification (8008), saga (8011) — alle tre *har* en `/health`-rute.
   De 26 workers har **ingen HTTP-overflade**, så et health-probe er ikke "manglende" for dem,
   det er strukturelt umuligt. Deres gate må være container-tilstand.

**Overclaim der skal undgås:** den nye worker-gate ville **ikke** have fanget banking. Banking
kørte, `/health` svarede 200 hele vejen, og PEM'en læses per request. Gaten fanger en *død*
container — en anden, i dag helt udækket klasse. Lektien fra bankings finding står uændret: et
liveness-probe kan ikke se en brudt afhængighed.

## Non-goals

- **Ingen ændring i hvad nogen test asserterer.** Alle 19 jobs skal blive grønne på samme
  grundlag som i dag; det eneste nye der kan gøre CI rød er de to nye gates, og kun på en
  tilstand der allerede er en fejl.
- **Intet nyt CI-job.** Worker-gaten hører i `e2e-tests`, som er det eneste job der har en
  compose-stak oppe — et nyt job ville koste en anden `compose up --build` (~6 min), samme
  argument som P2-39's decision-note bruger om browser-suiten.
- **Ingen health-endpoints på de 26 workers.** Det er en større ændring (P3-11 ejer
  worker-liveness-probes) og ikke nødvendig for at opdage en død container.
- **P3-46 (`qwen3:8b` OOM) løses ikke her.** Kun spørgsmålet om `ai-service` kan gates
  pålideligt inden for de 180 s berøres, og svaret må gerne blive nej.
- **P3-45 (nginx' cachede upstream-IP'er) røres ikke** — men forvent at ramme den under lokal
  verifikation; genstart `frontend` efter `up --build`, ellers diagnosticerer du 502'er.
- **Bankings adfærd ved konfigureret integration er uændret.** Kun statuskoden på
  "ikke konfigureret" flyttes; ingen ny logik i `EnableBankingClient`.
- **Ingen `pip`/lockfile-ændringer.** ES-fixturens timeout skal bruge den `testcontainers`
  4.14.2 der allerede er i `uv.lock`, ikke en opgradering.

## Steps

Commit per trin — rent rollback, jf. konventionen.

1. [x] **Mål baseline for de fire jobs, før nogen grænse sættes.** Ingen filændring.

   Målt over de 10 seneste grønne `ci.yml`-kørsler på master (28. juli), varighed per
   *job-instans* (matrix-jobs tæller hver deres kørsel, så n > 10):

   | job | n | p50 | max | max-bæreren | grænse |
   |---|---|---|---|---|---|
   | `repo-lint` | 10 | 10 s | 13 s | — | 5 min |
   | `python-services` | 120 | 26 s | **120 s** | analytics-service (p50 83 s) | 8 min |
   | `shared-packages` | 40 | 14 s | 20 s | — | 5 min |
   | `frontend` | 10 | 48 s | 56 s | — | 5 min |

   `e2e-tests` til reference: p50 268 s, max 328 s, under sin eksisterende grænse på 30 min.

   **Grænserne er ~3× målt max med et gulv på 5 min**, fordi 3× max på de tre billige jobs
   ville være 40-170 s — så stramt at en langsom `actions/setup-python` eller en npm-cache-miss
   ville gøre dem røde, og formålet er ikke at fange langsomhed. `python-services` får 8 min
   (3× × 120 s = 6 min, plus luft til at analytics' ES-image-pull varierer).

   **Det hængte analytics-job var 836 s = 13,9 min** — altså 7× sin egen max, og 1,7× den
   grænse der sættes her. Grænsen på 8 min ville have fanget det efter ~8 min i stedet for
   at lade det sidde til 360 min-loftet.

2. [x] **`timeout-minutes` på de fire jobs uden.** Fil: `.github/workflows/ci.yml` — fire
   linjer i `repo-lint` (`:32`), `python-services` (`:70`), `shared-packages` (`:216`),
   `frontend` (`:271`), hver med den målte baseline i kommentaren. Alle 5 job-definitioner
   har nu en grænse.

   **Kontrol kørt (run 30405860162, `workflow_dispatch` på en throwaway-branch):** `repo-lint`
   fik `timeout-minutes: 1` + et `sleep 120` som første step. Jobbet blev afbrudt efter
   **72 s** (22:48:07 → 22:49:21), `sleep`-steppet er det der stoppes og de øvrige seks steps
   `skipped`. Kontrollen og branchen er rullet tilbage og slettet lokalt + remote.

   Bemærk at et push til en ikke-master-branch **ikke** trigger `ci.yml` (`on.push.branches:
   [master, main]`) — kontrollen krævede `gh workflow run --ref`. Værd at vide for enhver
   fremtidig CI-kontrol i dette repo.

   **Aflæsningen afdækkede en begrænsning der skal stå her, ikke opdages næste gang:** en
   `timeout-minutes`-afbrydelse rapporteres af GitHub som **`cancelled`, ikke `failure`**, og
   joblogens eneste spor er `##[error]The operation was canceled.` — ordet *timeout* optræder
   ikke, og grænsen navngives ikke. Konsekvens: `gh run view --log-failed` returnerer **tomt
   med rc=1**, fordi der ikke er noget fejlet job at vise. Signalet er altså "job `cancelled`
   + varighed ≈ grænsen", ikke en selvforklarende besked.

   Det er stadig fixet itemet beder om — 360 min bliver 5-8 min, og en ikke-grøn kørsel
   blokerer — men diagnosen kræver at man sammenholder varighed med grænsen. Derfor er den
   målte baseline i kommentaren ved hver grænse ikke pynt: den er det der gør et `cancelled`
   job læseligt som *timeout* frem for som *nogen trykkede annuller*.

3. [x] **Wait-timeout på `es_container`.** Fil:
   `services/analytics-service/tests/integration/conftest.py`.

   **Delfixet var ikke nødvendigt, og det er målt frem for formodet.** Læsning af
   `testcontainers` 4.14.2 i servicens venv: `WaitStrategy.__init__` sætter selv
   `_startup_timeout = testcontainers_config.timeout`, som er `TC_MAX_TRIES` (120) ×
   `TC_POOLING_INTERVAL` (1) = **120 s**. Waiten var altså aldrig ubundet.
   Public API er `container.waiting_for(strategy)` + `strategy.with_startup_timeout(s)` —
   ikke `wait_for_logs(timeout=)`.

   **Kontrol 1 (wait rammer sin grænse):** en `ElasticSearchContainer` på `alpine:3.19` med
   `sleep 300`, så den starter men aldrig lytter på 9200, `with_startup_timeout(10)`.
   Resultat: `TimeoutError: HTTP endpoint not ready within 10.0 seconds. Endpoint:
   http://localhost:54665/. Method: GET. Expected status codes: {200}. Hint: Check if the
   service is listening on port 9200 …` efter 13,8 s. Altså **allerede** en læsbar
   pytest-fejl — planens acceptkriterium (b) var opfyldt af pakke-defaults.

   **Kontrol 2 var først blind, og det er selv en lektie.** Et tag på `:0.0.0-does-not-exist`
   fejlede efter 0,10 s i `_environment_by_version` (`ValueError: Unknown elasticsearch
   version given: 0`) — altså i versions-parsing, **før** pull-stien blev rørt. Instrumentet
   målte ikke det det skulle. Gentaget med `:8.99.99`, som parser som 8.x: `docker.errors.
   NotFound: 404 … not found` efter 1,67 s. Læsbar, hurtig.

   **Det afgørende: hængen lå ikke i waiten, og de 836 s beviser det.** Var den i
   wait-strategien, var jobbet fejlet efter 120 s. At det sad 836 s viser at hængen lå i
   `docker_client.run(...)`'s **image-pull**, som kaldes før wait-strategien og er ubundet —
   og som 4.14.2 ikke eksponerer nogen knap for. Samme gælder Ryuk-containeren.

   **Hvad der så blev ændret:** grænsen skrevet eksplicit (`ES_STARTUP_TIMEOUT_S = 120`, samme
   værdi, så adfærden er uændret) som en **pin** mod at defaulten eller de to env-vars flytter
   sig uden at nogen rører filen — plus en kommentar der siger hvor grænsen *ikke* rækker, så
   fixet ikke foregiver at være komplet. Den reelle grænse for pull-klassen er trin 2's
   `timeout-minutes: 8`.

   `make -C services/analytics-service test`: **123 passed, rc=0** — normal sti uændret.
   Ruff check + format: rc=0.

   **Konsekvens for findingen (trin 8):** påstanden *"uden nogen wait-timeout. testcontainers
   venter så på ES' readiness uden en øvre grænse"* (finding, punkt 1) er **forkert** og skal
   rettes. Det er det tredje forkerte tal i dette item.

4. [x] **De tre ugatede HTTP-services ind i `Wait for system`.** Alle tre tilføjet — 8007
   (ai), 8008 (notification), 8011 (saga). Loopet dækker nu 8001-8012 uden huller.
   Alle tre har en `/health`-rute, verificeret; alle tre svarede 200 lokalt.

   **8007 blev inkluderet, og planens bekymring var inverteret — målt, ikke antaget.**
   Bekymringen var at `ai-service` ikke kunne nå de 180 s, fordi den har
   `depends_on: ollama-pull: condition: service_completed_successfully` (verificeret i
   `docker-compose.yml:560-566`), altså venter på en cold pull af qwen3:4b + bge-m3 = 3,7 GB,
   og CI cacher ikke ollama (`grep -i ollama .github/workflows/ci.yml` = 0 hits).

   Men `docker compose up -d` **blokerer selv** på den betingelse, så pullet betales i
   `Start system` — **målt 173 s / 181 s / 183 s** over tre kørsler (30405098099,
   30404527271, 30401900305) — og er færdigt *før* de 180 s i `Wait for system` begynder at
   tælle. Det er også derfor `Wait for system` kun er **3-7 s** i dag. 8007 er altså gratis.
   Hvis pullet en dag ikke lykkes, rammer fejlen `Start system`, som allerede er rød ved en
   fejlet `depends_on`-betingelse — ikke denne deadline.

   **Et blindspor undervejs, værd at have skrevet ned:** `ollama list` lokalt viste `qwen3:4b`
   og `bge-m3` med mtime "34 sekunder siden", hvilket lignede en cold pull under mit `up`.
   Det var det ikke — `ollama-pull`-containeren kørte start→finish i **2 s**, så modellerne
   var allerede i volumet, og `ollama pull` opdaterer manifestets mtime på et no-op. En lokal
   måling kan derfor **ikke** besvare 8007-spørgsmålet; det var CI's `Start system`-varighed
   der gjorde det.

   **Kontrol:** `docker compose stop saga-service` → loopet fejlede på 8011 med
   `::error::Service on port 8011 did not become healthy` mens 8007 og 8008 passerede.
   Saga genstartet, 200 igen.

5. [x] **Worker-gaten: ingen container må være exited nonzero eller i restart-loop.**
   Ny fil `scripts/compose_state_check.py` (Python frem for inline-`jq`, samme konvention som
   `scripts/compose_check.py`, som `repo-lint` allerede linter) + nyt step
   `Check no container is dead or restarting` i `e2e-tests`, placeret **efter
   `Wait for system` men før testene** — en død worker skal rapporteres som en død worker,
   ikke som den downstream-assertion der tilfældigvis fejler af den. Plus
   `make compose-state-check` så gaten kan køres lokalt.

   **Fælden var reel:** `ollama-pull` står `exited` med `exit=0` på en korrekt stak — målt som
   den eneste ikke-`running` af 53 containere. Prædikatet er derfor nonzero-exit, ikke
   not-running, og gatens grønne output navngiver den eksplicit som forventet ren exit.

   **Kontrollen afdækkede at planens overskrifts-prædikat alene ville have været blindt.**
   `saga-timeout-worker` med en uopnåelig `DATABASE_URL` rapporteres af compose som
   `State: restarting` med **`ExitCode: 0`** — fordi 25 af de 53 services er
   `restart: on-failure` og derfor cykler frem for at sætte sig i `exited`. En
   "exited nonzero"-only gate havde altså været grøn på præcis den fejl den findes for.
   Det er `restarting`-klausulen der fanger den, og begrundelsen står nu i scriptet.

   Begge grene verificeret rødt, hver for sig:
   - `restarting`: uopnåelig `DATABASE_URL` → rc=1, `saga-timeout-worker (…): state=restarting`
   - `exited nonzero`: `restart: "no"` + `sys.exit(3)` → rc=1, `… : exited with code 3`
   - uændret stak: **rc=0**, 53 containere, `ollama-pull` navngivet som forventet ren exit

   Begge kontroller kørt via throwaway compose-override-filer i scratchpad, så
   `docker-compose.yml` aldrig blev rørt. Workeren er genoprettet og gaten er grøn.

   Ingen pipe gennem `tail`/`head` nogen steder; `rc` aflæst eksplicit i hver kontrol.

6. [x] **P2-42a: `BankConfigError` → 503 + WARNING.** Ny
   `@app.exception_handler(BankConfigError)` i `main.py`, og de to per-rute `status_code=500`
   fjernet fra `/available-banks` og `/connect` i `bank_api.py`. `/callback`s
   `except BankConfigError` (`:175`) er **urørt** — den returnerer et browser-redirect med
   `code=config_error`, ikke en statuskode, og er en anden ting.

   **Kæden bekræftet ved reproduktion, og den var værre end planen beskrev.** De to nye tests
   var først røde med `BankConfigError: PEM key not found at /nonexistent/enablebanking.pem`
   som en **uhåndteret exception** — altså undslap den dependency-resolutionen helt.
   Konsekvens planen ikke nævnte: rutens *eget* `except BankConfigError` på `/available-banks`
   har **aldrig** fanget den manglende PEM. Det blokerede kun config-fejl der opstår *inde i*
   servicekaldet, fx JWT-signering (`enable_banking_client.py:102`). Så begge ruter gav 500 ad
   samme vej, og de to `status_code=500` var døde for netop denne fejlklasse.

   **Tests (2 nye, 68 → 70):** de overrider bevidst **ikke** `get_banking_service`, for det er
   hele pointen — fejlen skal kastes af den *rigtige* dependency. Kun `get_db` overrides, da
   den resolves først og ikke er hvad testen handler om. Begge verificeret røde før handleren,
   grønne efter. `make -C services/banking-service check`: **rc=0**, 59 unit + 11 integration.
   (Testene kører fint lokalt; note til P3-39's antagelse.)

   **Live-verificeret gennem containeren, ikke kun i pytest.** `make check` er statisk og
   importerer ikke `app.main` under imagets versioner — og dette trin tilføjer netop et nyt
   top-level-import i `main.py`, hvor en cykel først ville vise sig ved opstart.
   `docker compose up -d --build banking-service` → `running healthy`, ren opstartslog.
   Derefter med `ENABLE_BANKING_KEY_PATH` peget på en ikke-eksisterende PEM via
   compose-override:
   - `GET /api/v1/bank/available-banks?country=DK` → **HTTP 503**
   - `GET /api/v1/bank/connections?account_id=1` → **HTTP 503** (den der gav 500)
   - begge med `{"detail":"Bank-integrationen er ikke tilgængelig lige nu. Prøv igen senere."}`
   - logget som `Enable Banking not configured — returning 503: PEM key not found at …`,
     altså WARNING med den konkrete config-fejl navngivet

   **Retryable bekræftet frem for antaget:** to requests gav **to** log-linjer, så
   `_banking_client` latcher ikke — hver request forsøger konstruktionen igen. Det er den
   semantik 503 lover og 500 ikke gør. Banking genoprettet bagefter: `/connections` → 200.

   **Det åbne valg er afgjort til (b), målt.** `Run browser tests` er **success** i alle tre
   seneste kørsler, og `Generate throwaway Enable Banking key` ligeså — så banking *er*
   korrekt konfigureret i CI, der er ingen 5xx at undtage, og (a) ville være unødig
   kompleksitet. P2-39's 5xx-vagt røres ikke.
   Konsekvensen der skal siges højt: **503-stien er dermed ikke dækket i CI.** Den er dækket
   af de to nye tests. Hvis PEM-steppet en dag fjernes, vil browser-suiten rapportere 503 som
   5xx — og det er den rigtige adfærd, ikke en fejl at undtage.

7. [x] **Verifikation samlet.** `make compose-check` (rører vi compose eller
   dependency-filer), `make -C services/banking-service check`, `make test-e2e` (24 forventet),
   `make test-browser` (4 forventet), og CI grøn på hele stakken. **Aflæs de nye steps
   navngivet i loggen** — "success" siger ikke i sig selv at worker-gaten kørte, kun at jobbet
   sluttede. Det er samme aflæsning P2-40 lavede for sin nye spec.

8. [x] **Docs.** Luk P2-38 og P2-42's a-halvdel i `BACKLOG.md` (rows = pointere, ikke
   rapporter), fyld **Outcome** her, opdatér `STATUS.md`, ret de to forkerte tal i
   findings/backlog (`timeout-minutes` = 1 ikke 0; nævneren 12 HTTP-services ikke 53), og
   `make notes-check` før commit.

## Risks & rollback

| Risiko | Detektion | Rollback |
|---|---|---|
| En `timeout-minutes` sat for stramt gør et normalt job rødt | Jobbet fejler med *timed out* uden en reel hængning | Hæv tallet; grænsen er én linje per job |
| Trin 4 gør CI rød fordi `ai-service` er langsom i CI | `Wait for system` fejler på 8007 | Udelad 8007 (planlagt udfald, ikke en fejl) |
| Worker-gaten er rød på en korrekt stak (`ollama-pull`) | Første kørsel efter trin 5 | Prædikatet er nonzero-exit; juster eller fjern steppet |
| 503 fra banking brækker `BankConnectionWidget` | Frontenden håndterer allerede fejlen og render en tilstand; browser-suitens 5xx-vagt vil dog **rapportere** 503'eren | Sidste ende: revert trin 6; men se note nedenfor |
| ES-timeouten maskerer en langsom-men-virkende ES lokalt | `make -C services/analytics-service test` bliver rød uden ændring i analytics-kode | Hæv grænsen |

**Åbent valg der skal afgøres i trin 6, ikke antages:** P2-39's browser-fixtur fejler på
**enhver 5xx** med URL. Et 503 er stadig 5xx, så suiten vil fortsat rapportere banking i CI —
nu blot med en ærlig kode. Der er to legitime udfald: (a) fixturen skal undtage 503 fra en
valgfri integration, eller (b) CI's throwaway-PEM gør spørgsmålet teoretisk, fordi banking er
korrekt konfigureret i CI efter P2-39. **(b) er sandsynligvis rigtigt** — PEM'en genereres nu —
men det skal *måles*, ikke formodes: hvis suiten er grøn i CI i dag, er der ingen 5xx at undtage,
og så er (a) unødig kompleksitet.

## Outcome

**Shippet 2026-07-29 i seks commits (`a1bf5855`..`8d4cd472`), plus docs.** Alle fire
delkriterier er leveret, men **kriterium (b) blev leveret som et negativt resultat** — fixturen
manglede ikke det planen antog. Se trin 3.

### Hvad der virker nu

| Kriterium | Status | Verificeret ved |
|---|---|---|
| (a) `timeout-minutes` efter målt varighed på hvert job | ✅ alle 5 | `repo-lint` med grænse 1 + `sleep 120` → afbrudt efter 72 s (run 30405860162) |
| (b) `es_container` fejler læsbart frem for at hænge | ✅ **var allerede sandt** | container der starter men ikke lytter → læsbar `TimeoutError` efter 13,8 s |
| (c) `e2e-tests` fejler på exited-nonzero/restart-loop | ✅ | begge grene verificeret rødt hver for sig; uændret stak grøn |
| (d) banking svarer 503 + WARNING | ✅ | live gennem containeren: begge ruter → 503, WARNING navngiver config-fejlen |

Lokalt grønt: `make test-e2e` **24 passed**, `make test-browser` **4 passed**,
`make -C services/banking-service check` rc=0 (59 unit + 11 integration, 68 → **70**),
`make -C services/analytics-service test` **123 passed**, `make compose-check` rc=0,
`make notes-check` rc=0, repo-bred `ruff check` + `format --check` rc=0 (666 filer).

### De tre forkerte tal, rettet frem for pyntet

Planen forudsagde to; der var tre.

1. `grep -c timeout-minutes ci.yml` gav **1**, ikke 0 (P2-39 havde sat den på `e2e-tests`).
2. Nævneren er **12 HTTP-services**, ikke 53.
3. **Nyt:** findingens punkt 1 — *"uden nogen wait-timeout … uden en øvre grænse"* — er forkert.
   `testcontainers` 4.14.2 bounder waiten til 120 s og fejler meget læsbart.

### Det vigtigste enkeltfund

**Worker-gatens prædikat kan ikke være "exited nonzero" alene.** En worker med uopnåelig
`DATABASE_URL` rapporteres af compose som `restarting` med **`ExitCode: 0`**, fordi 25 af de 53
services er `restart: on-failure` og cykler frem for at sætte sig i `exited`. Havde jeg
implementeret planens overskrifts-prædikat og kun kørt kontrollen for `ollama-pull`-fælden, var
gaten blevet grøn på præcis den fejlklasse den findes for at fange. Det er samme fejlmode som
itemet handler om, én lag længere inde — og det er grunden til at *begge* grene blev verificeret
hver for sig frem for at én rød kørsel blev taget som bevis for gaten.

### Fire ting hvor målingen modsagde planen

- **De 836 s beviser hvor hængen *ikke* var.** En hængende wait var fejlet efter 120 s. Altså lå
  den i `docker_client.run(...)`'s image-pull, som kaldes før wait-strategien og er ubundet uden
  nogen knap i 4.14.2. Det gør `timeout-minutes` til den *eneste* grænse for klassen — ikke
  "begge grænser i serie" som findingen foreslog — og det gør den foreslåede image-cache mere
  relevant, ikke mindre.
- **8007 var gratis, ikke dyr.** Bekymringen var at `ai-service`s
  `service_completed_successfully`-afhængighed af et 3,7 GB ollama-pull ikke kunne nå de 180 s.
  Men `docker compose up -d` blokerer selv på den betingelse, så pullet betales i `Start system`
  (målt 173/181/183 s) og er færdigt før deadlinen begynder at tælle — derfor er
  `Wait for system` kun 3-7 s.
- **Bankings rute-`try/except` var død, ikke blot overflødig.** Planen sagde at handleren
  "dækker" de to `status_code=500`. Reproduktionen viste at de aldrig havde fanget en manglende
  PEM: fejlen kastes under dependency-resolution, så de blokerede kun config-fejl *inde i*
  servicekaldet (JWT-signering). Begge ruter gav 500 ad samme vej.
- **Det åbne valg blev (b), målt.** `Run browser tests` er success i alle tre seneste kørsler og
  PEM-steppet ligeså, så banking *er* konfigureret i CI, der er ingen 5xx at undtage, og (a)
  ville være unødig kompleksitet. Konsekvensen der skal siges højt: **503-stien er dermed ikke
  dækket i CI** — den er dækket af de to nye tests.

### Instrumenter der var blinde undervejs

Tre gange målte jeg noget andet end det jeg troede. Værd at have skrevet ned, fordi mønsteret er
det samme som [[project_measurement_instrument_validity]]:

1. **Kontrol 2 i trin 3:** et image-tag på `:0.0.0-does-not-exist` fejlede i versions-parsing
   efter 0,10 s, altså **før** pull-stien blev rørt. Gentaget med `:8.99.99`, som parser som 8.x.
2. **`ollama list`s mtime:** `qwen3:4b` og `bge-m3` stod "34 sekunder siden", hvilket lignede en
   cold pull. Men `ollama-pull`-containeren kørte start→finish i **2 s** — modellerne var
   cachede, og `ollama pull` opdaterer mtime på et no-op. Lokal måling kunne derfor ikke besvare
   8007-spørgsmålet; CI's step-varighed kunne.
3. **`make test | tail -5`:** viste "9 passed" og fik banking til at se ud som om kun
   integrationstestene kørte. `make test` kører unit og integration som to pytest-kald, så
   trunkeringen skjulte de første 59. Samme fælde som
   [[feedback_pipe_hides_exit_code]], nu 7×.

### Efterladt

- **P2-42's b-halvdel er fortsat open.** Den nye worker-gate ville **ikke** have fanget banking:
  servicen kørte, `/health` svarede 200 hele vejen, og PEM'en læses per request. Gaten fanger en
  *død* container — en anden, hidtil udækket klasse. Et liveness-probe kan stadig ikke se en
  brudt afhængighed.
- **`Health: unhealthy` er bevidst udenfor gatens prædikat**, begrundet i scriptets docstring:
  HTTP-servicene er allerede dækket af `Wait for system`, og at tage det med ville gøre samme
  fejl rød to gange plus risikere en ny flake-klasse på langsomt startende healthchecks.
- **Ingen `.dockerignore` i repoet**, så hele arbejdstræet — inkl. den gitignorerede
  `enablebanking-sandbox.pem` — sendes til Docker-dæmonen som build-kontekst ved hvert
  `up --build`. Ikke en læk (dæmonen er lokal, og ingen Dockerfile bruger bred `COPY .` —
  empirisk verificeret at banking-imaget kun indeholder CA-bundles), men et manglende værn og
  langsommere builds. Ikke et item endnu.
- **Den lokale sandbox-PEM står `-rw-r--r--` (644).** CI's er throwaway så 644 er fint dér, men
  den rigtige nøgle lokalt burde være 600. Ikke et item endnu.
- **`analytics-service`s venv kører Python 3.14 lokalt mod 3.11 i CI** (`requires-python
  >=3.11`). Faldt over det under trin 3; ikke undersøgt, ikke rørt. Kandidat til et item, da
  "virker lokalt, ikke i deploy" er en navngivet tema i CLAUDE.md.

### CI grøn, og de nye steps aflæst navngivet — ikke kun "success"

**Run 30407613111 på `8d4cd472`: alle 19 jobs success.** Aflæsningen planen krævede, fordi
"success" i sig selv ikke siger at en ny gate *kørte*:

- **Worker-gaten kørte med sit rigtige output:** `compose-state-check: 53 containers, none dead,
  exited nonzero, or restarting. Exited cleanly (expected): ollama-pull.` Altså 53 containere
  faktisk inspiceret i CI, og `ollama-pull`-fælden håndteret i det rigtige miljø — ikke kun
  lokalt, hvor den blev designet.
- **Alle 12 porte + 3000 aflæst `healthy`**, inkl. de tre nye: `port 8007: healthy`,
  `port 8008: healthy`, `port 8011: healthy`. Ingen huller i 8001-8012.
- **Steppet er navngivet i job-listen:** `Check no container is dead or restarting: success`,
  placeret mellem `Wait for system` og `Run E2E tests` som planlagt.
- `Run E2E tests` 24 passed, `Run browser tests` 4 passed.

**Varigheder mod de nye grænser** — rigelig luft, ingen grænse i nærheden af at ramme:

| job | målt i denne kørsel | grænse |
|---|---|---|
| `repo-lint` | 17 s | 5 min |
| `shared-packages` | max 23 s | 5 min |
| `python-services` | max 82 s (analytics) | 8 min |
| `frontend` | 50 s | 5 min |
| `e2e-tests` | 314 s | 30 min |

**Det åbne valg endeligt afgjort til (b), målt i CI:** `grep -cE "http 5[0-9][0-9]: (GET|POST|…)"`
på browser-jobbets log giver **0**, og `console.error` giver **0**. Browser-fixturens 5xx-vagt
har altså intet at rapportere — banking *er* korrekt konfigureret i CI, så der er ingen 503 at
undtage, og (a) ville have været unødig kompleksitet. P2-39's fixtur er urørt.

**En fjerde blind måling, undervejs i netop denne aflæsning:** mit første forsøg,
`grep -icE "5xx|503"`, gav **41 hits** og lignede et problem. De var alle falske — `503`
optræder inde i GitHubs tidsstempler (`23:20:57.5031628Z`). Det rigtige instrument er fixturens
egen ordlyd, `http <status>: <method> <url>`. Samme lektie som de tre andre i afsnittet ovenfor,
og denne gang på selve *kontrol*-aflæsningen — jf. [[feedback_baseline_can_be_accidentally_right]].
