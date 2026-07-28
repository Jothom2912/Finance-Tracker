---
title: P2-38 + P2-42 — CI's manglende signal: jobtimeouts, ES-fixturens wait-timeout, døde workers og bankings 500→503
date: 2026-07-29
status: open
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

3. [ ] **Wait-timeout på `es_container`.** Fil:
   `services/analytics-service/tests/integration/conftest.py:19-24`.
   Find først den knap `testcontainers` **4.14.2** faktisk eksponerer (`testcontainers_config`
   / `TC_MAX_TRIES` / `wait_for_logs(timeout=)`) ved at læse pakken i servicens venv — *gæt
   ikke på API'et*, versionen er nyere end de fleste eksempler.
   **Vær eksplicit om hvad denne grænse ikke dækker:** i den hængte kørsel kom containeren
   aldrig op, og et image-**pull** sker i docker-py før wait-strategien. Bounder den kun
   waiten, er trin 2 stadig den ydre og pålidelige grænse — og så skal *det* stå i kommentaren
   frem for at fixet foregiver at være komplet.
   **Kontrol:** peg fixturen på et ikke-eksisterende image-tag → skal fejle med en læsbar
   pytest-fejl inden for grænsen, ikke hænge. Kør `make -C services/analytics-service test`
   bagefter for at bekræfte at den normale sti er uændret (123 tests).

4. [ ] **De tre ugatede HTTP-services ind i `Wait for system` — hvis de kan bære det.**
   Fil: `.github/workflows/ci.yml` (`Wait for system`-loopet, `ci.yml:369`). Tilføj 8007
   (ai), 8008 (notification), 8011 (saga).
   **Måles før den bliver hård:** `ai-service` afhænger af `ollama-pull`, som puller `qwen3:4b`
   + `bge-m3`. Kan `/health` på 8007 ikke nås inden for de 180 s i CI, så **udelad 8007 med en
   navngivet grund i kommentaren** frem for at hæve deadlinen blindt — en hævet deadline gør
   trin 2's grænse til den der rammer, og det er en dårligere fejlbesked. Notification og saga
   har ingen tunge afhængigheder og forventes gratis.
   **Kontrol:** `docker compose stop saga-service` lokalt → loopet skal fejle på 8011 med
   `docker compose ps` i outputtet.

5. [ ] **Worker-gaten: ingen container må være exited nonzero eller i restart-loop.**
   Nyt step i `e2e-tests` efter `Wait for system`, plus muligvis en lille parser i
   `scripts/` hvis inline-`jq` bliver ulæselig. `docker compose ps --all --format json` →
   fejl hvis nogen container har `State: exited` med nonzero exit code, eller `restarting`.
   **Fælden der skal håndteres eksplicit:** `ollama-pull` er `restart: "no"` og **exit 0** når
   den er færdig (`docker-compose.yml:137-145`), så prædikatet skal være *nonzero exit*, ikke
   *not running*. Ellers er gaten rød på en korrekt stak fra første kørsel.
   Læs `rc=$?` eksplicit; **ingen pipe gennem `tail`/`head`** — den fælde har ramt 6×, senest
   på selve kontrol-aflæsningen.
   **Kontrol (den vigtigste i planen, fordi gaten ellers er grøn-på-ingenting):** knæk én
   worker med vilje — fx en ugyldig `DATABASE_URL` på `saga-timeout-worker` — og bekræft at
   steppet bliver **rødt og navngiver containeren**. Bekræft derefter at en uændret stak er
   grøn, altså at `ollama-pull` ikke udløser den.

6. [ ] **P2-42a: `BankConfigError` → 503 + WARNING.** Filer:
   `services/banking-service/app/main.py` (nyt `@app.exception_handler(BankConfigError)` ved
   siden af de seks der allerede findes, `main.py:34-62`) og
   `services/banking-service/app/adapters/inbound/bank_api.py` (fjern de to per-rute
   `status_code=500` på `:95` og `:118`, som handleren nu dækker).
   **Hvorfor handleren og ikke en try/except:** `GET /connections` (`bank_api.py:205-212`) har
   **ingen** try/except og kan ikke få en der virker — `BankConfigError` kastes i
   `Depends(get_banking_service)` → `_get_banking_client()` → `EnableBankingClient.__init__`
   (`dependencies.py:33`, `enable_banking_client.py:73`), altså **før** rutens krop.
   Det er derfor dashboardets kald giver 500. Trin 1 i dette trin er at bekræfte den kæde ved
   at reproducere 500'eren lokalt.
   Bemærk at `_banking_client`-singletonen forbliver `None` når konstruktionen kaster, så hver
   request forsøger igen — hvilket er den rigtige semantik for en 503 (retryable).
   **Tests:** banking-service har ingen dækning af denne sti. Tilføj mindst to:
   `/bank/connections` med ulæselig PEM → 503, og `/available-banks` → 503 (den der før gav
   500). **Verificér dem røde** uden handleren.
   `make -C services/banking-service test` (68 passed i dag, kun i CI iflg. P3-39 — kør det
   der arbejder).

7. [ ] **Verifikation samlet.** `make compose-check` (rører vi compose eller
   dependency-filer), `make -C services/banking-service check`, `make test-e2e` (24 forventet),
   `make test-browser` (4 forventet), og CI grøn på hele stakken. **Aflæs de nye steps
   navngivet i loggen** — "success" siger ikke i sig selv at worker-gaten kørte, kun at jobbet
   sluttede. Det er samme aflæsning P2-40 lavede for sin nye spec.

8. [ ] **Docs.** Luk P2-38 og P2-42's a-halvdel i `BACKLOG.md` (rows = pointere, ikke
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

## Outcome (fill in when done)
