---
title: P2-39 — browser-automatisering som ejet instrument (@playwright/test, to tests)
date: 2026-07-28
status: done
backlog-items: [P2-39]
related:
  - ../decisions/2026-07-28-browser-automation-instrument.md
  - ../findings/2026-07-28-graphql-client-rejects-relative-url.md
  - ../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md
  - ../findings/2026-07-27-sync-trigger-double-value.md
---

# P2-39 — browser-automatisering som ejet instrument

## Goal

Repoet får et **tredje instrument**: en browser der driver den byggede app bag perimeteren, ejet
som kode og kørt i CI. Færdig når (a) to tests kører mod `http://127.0.0.1:3000` i det
eksisterende `e2e-tests`-job og er **hårde gates**, (b) hver af de to er **verificeret rød ved en
navngivet mutation**, og (c) P3-25's C2-kontrol — at `'unsafe-inline'` er nødvendig *i appen* —
er afgjort med et tal frem for at stå som åben ende.

Ikke færdig hvis suiten kun er grøn. En browser-test der aldrig er set fejle er værre end ingen,
fordi den ligner dækning — det var præcis fejlmoden i P1-16.

## Context

[Decision-noten](../decisions/2026-07-28-browser-automation-instrument.md) traf valget:
`@playwright/test` i `services/frontend/`, kørt i `e2e-tests` frem for i et nyt job (som ville
koste en anden fuld `compose up --build`). Tre alternativer afvist dér.

Motivationen er målt, ikke formodet: begge eksisterende suiter — 346 jsdom-tests og 24 Python-e2e
— var **grønne gennem hele P1-16**, hvor hver bruger så
`Fejl: Failed to construct 'URL': Invalid URL` i stedet for data
([finding](../findings/2026-07-28-graphql-client-rejects-relative-url.md)). Og P3-25's ad hoc
headless-Chrome-probe fandt bug'en, men er ikke checket ind og **kan ikke klikke**
([P3-25 trin 6](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md)).

## Non-goals

- **De 346 jsdom-tests røres ikke.** Ingen portering, ingen sletning, ingen afmockning.
  `graphqlClient.test.jsx:12` bliver ved at mocke `GraphQLClient` — den mock er legitim for
  401-interceptoren. Det brede afmocknings-arbejde er P3-41.
- **`tests/e2e/` røres ikke.** Den rammer porte direkte og går uden om perimeteren *med vilje*
  (`nginx.conf:51`); det er dens værdi som kontrol.
- **Ingen produktkode ændres.** Rammer vi produktkode, er det et fund, ikke et trin — det får sin
  egen finding og sit eget item, som P1-16 fik.
- **Ingen ændring af `nginx.conf`, CSP-direktiver eller rate limits.** Hvis C2 viser at
  `'unsafe-inline'` *ikke* er nødvendig, er fjernelsen et separat item — måling først.
- **Ingen ny CI-job og ingen `compose up` nummer to.**

## Steps

1. [x] **Playwright ind som devDependency + config.** `services/frontend/package.json`
   (`@playwright/test`, script `test:browser`), ny `services/frontend/playwright.config.js`:
   `testDir: './e2e'`, `baseURL: 'http://127.0.0.1:3000'` (**ikke** `localhost` — P3-43's første
   måling ramte en Vite dev-server på `[::1]:3000`), `workers: 1`, `retries: 0`,
   `trace: 'on-first-retry'` → `'retain-on-failure'`, kun `chromium`.
   `testDir` skal ligge uden for `src/`, så vitests glob ikke opsamler dem — verificér at
   `npm test` stadig kører **346** og ikke 346 + n. `.gitignore`: `test-results/`,
   `playwright-report/`.

2. [x] **Fixturen der ejer session-seedingen** — `services/frontend/e2e/fixtures/session.js`.
   Signerer HS256 med `JWT_SECRET` (samme mønster som `tests/e2e/_env.py:19-39`) og sætter alle
   **fem** nøgler fra `authStorage.js:1` via `addInitScript`, altså før appen mounter.
   `account_id` + `account_name` er ikke valgfrie: uden dem sender `apiClient` ingen
   `X-Account-ID` og `periodOverview` svarer med **tavse nuller i stedet for en fejl** — en
   grøn-udseende test på en tom app. Fixturen skal derfor selv asserte at seedingen tog, ikke
   antage det. Bruger/konto seedes via API mod portene (som `tests/e2e/` gør), ikke via UI-flow.

3. [x] **Test 1 — P1-16-klassen.** `e2e/dashboard-loads-real-data.spec.js`: seedet session +
   kendt transaktionsbeløb → dashboardet viser **det tal**. Assertionen skal ramme et beløb, ikke
   at siden mounter; `TypeError: Invalid URL` gav et *mountet* DOM med en fejltekst i.
   Fang samtidig `page.on('pageerror')` og `console` og fejl testen på dem — det er det signal de
   346 ikke har.

4. [x] **Test 2 — CSP håndhæves i appen (P3-25's C2).** `e2e/csp-enforced.spec.js`: lyt på
   `securitypolicyviolation` via `addInitScript`, åbn en radix-dialog (klikket proben ikke kunne),
   assertér **nul** violations. Kør den derefter mod en stak uden `'unsafe-inline'` på
   `style-src`; det er C2-målingen, og udfaldet noteres som et tal uanset retning. Om mutationen
   sker via en throwaway-nginx (P3-25's metode) eller en env-parametriseret config afgøres i
   trinnet — men den skal kunne gentages uden uoprydt tilstand i dev-stakken.

5. [x] **Mutations-kontrol, før CI.** Test 1: genindfør P1-16 i `graphqlClient.jsx` (relativ URL)
   → forvent rød, og forvent at `npm test` samtidig er **grøn** — det er beviset for at
   instrumentet er nyt og ikke overlappende. Test 2: `script-src 'none'` → forvent violation og en
   app der ikke mounter (P3-25's kendte kontrol-udfald). Læs `rc=$?` eksplicit; **ingen pipe
   gennem `tail`/`head`** — den fælde har ramt 6×, senest på selve kontrol-aflæsningen.

6. [x] **CI: udvid `e2e-tests`** (`ci.yml:279-344`) — ikke et nyt job.
   `actions/setup-node@v4` (node 20, npm-cache på `services/frontend/package-lock.json`),
   `npm ci`, `npx playwright install --with-deps chromium` med cache på `~/.cache/ms-playwright`,
   **port 3000 tilføjet til `Wait for system`-loopet** (det poller i dag kun 8001-8012, så
   browser-suiten kan i princippet starte mod en frontend der ikke er oppe), og
   `npm run test:browser` efter `Run E2E tests`. Upload `playwright-report/` som artifact
   `if: failure()`. Jobbets `JWT_SECRET: test-secret` er allerede sat og er den fixturen skal læse.

7. [x] **`Makefile`:** `make test-browser`, og ret `Makefile:49,91` som siger port **5173** hvor
   frontenden reelt er 3000 — den forkerte port i hjælpeteksten er en fælde af samme slags som
   den vi automatiserer os ud af.

8. [x] **Ryd P3-25's efterladenskaber.** Bruger `csp_probe` (id 368), konto 371 og 5
   transaktioner blev bevidst ikke ryddet op, fordi de var forudsætningen for at gentage
   browser-verifikationen. Når fixturen ejer seedingen, er de gæld — slet dem, og bekræft at
   suiten stadig er grøn *bagefter* (ellers seeder fixturen ikke det den påstår).

9. [x] **Verifikation** — se afsnittet nedenfor. Docs til sidst: STATUS.md, backlog-rækken,
   session-log.

**Commits:** én per trin-gruppe, jf. husreglen — (1-2) opsætning + fixture, (3) test 1,
(4) test 2, (6) CI, (7-8) Makefile + oprydning, docs.

## Verification

Kommandoerne der tæller, med forventet udfald:

| Hvad | Kommando | Forventet |
|---|---|---|
| Browser-suiten grøn lokalt mod fuld stak | `docker compose up -d --build` + `make test-browser` | 2 passed |
| Instrumentet er **nyt**, ikke overlappende | P1-16 genindført → `npm test`; `make test-browser` | **346 passed** / **1 failed** |
| Test 2 kan se en violation | `script-src 'none'` → `make test-browser` | violation + app mounter ikke |
| C2 afgjort | `style-src` uden `'unsafe-inline'` → dialog åbnes | antal violations, som **tal** |
| Ingen regression i de andre to suiter | `npm test`, `make test-e2e` | 346 passed, 24 passed |
| CI | `make ci-status` | alle jobs grønne, `e2e-tests` viser 2 browser-tests **navngivet** |
| Notes | `make notes-check` | grøn |

**Fald ikke for `curl`-fælden i omvendt retning:** en grøn browser-suite beviser klienten, ikke
transporten. De to andre suiter bliver ikke redundante af dette.

## Risks & rollback

- **Flake er ny for dette repo.** Modtræk: `workers: 1`, `retries: 0` (en retry der skjuler flake
  er samme fejlmode som en mock der skjuler en bug), og suiten holdt på to tests. Fejler den
  ikke-deterministisk i CI to gange uden kodeændring, er *det* fundet — noter det, lad være med at
  hæve retries.
- **`e2e-tests`-jobbets varighed vokser** (~30-60 s browser-install + suiten). Jobbet har i dag
  **intet `timeout-minutes`** (→ P2-38), så en hængende browser hænger i 6 timer uden signal.
  Overvej at lade P2-39 sætte `timeout-minutes` på netop dette job som et sideprodukt — det er
  billigt her og gør risikoen selvbegrænsende. Afgøres i trin 6.
- **Frontend-imaget i compose er en produktions-build.** Ændres `Dockerfile` eller
  `nginx.conf` senere, fejler suiten på noget der ser ud som en test-fejl. Det er ønsket adfærd.
- **Rollback er billig og total:** alt nyt ligger i `services/frontend/e2e/`,
  `playwright.config.js`, tre linjer i `package.json` og fire steps i `ci.yml`. Ingen produktkode,
  ingen migration, intet schema. Fjern steppene fra `ci.yml` for at afgate uden at slette suiten.

## Outcome

**Shippet 2026-07-28** i syv commits (`35f2e047`, `c2e4a6ae`, `d632f1e9`, `90a11e3c`,
`cb9d6974`, `ce339e5f`, `9ea54d38` + docs). Ingen produktkode ændret — `git diff` mod HEAD
var tom efter hver mutations-kontrol.

**Instrumentet:** 3 tests i `services/frontend/e2e/`, hård gate i `e2e-tests`, 15-16 s lokalt.

| Verifikation | Udfald |
|---|---|
| Browser-suiten mod fuld stak | **3 passed** (planlagt 2 — fixturen fik sin egen vagt) |
| Instrumentet er **nyt** (`totalIncome → totalIncomeTYPO`) | `npm test` **346 passed**, browser **2 failed** |
| Test 2 kan se en violation (`script-src 'none'`) | violation-stien nås ikke — appen mounter ikke; rød på kort/dialog |
| **C2 afgjort** (`style-src` uden `'unsafe-inline'`) | **1 violation**, `style-src-elem`/inline, ved dialog-klik · **0** på `/dashboard` |
| Ingen regression | `npm test` 346 passed, `make test-e2e` 24 passed |
| `make notes-check` | 136 notes, no problems |
| **CI grøn med suiten som gate** | run `30400981674`: 3 browser-tests **navngivet**, 18,9 s + 24 Python-e2e |

### Hvad planen fik forkert

**Færdig-kriteriets egen kontrol holdt ikke.** Planen forventede at P1-16 genindført gav
"346 passed / 1 failed". Målingen: **2 af 346 fejlede også**. P1-16 fik sin egen
jsdom-regressionstest (`graphqlClient.url.test.jsx`) da den blev rettet, så linjen er
dobbeltdækket i dag. En anden kandidat — `X-Account-ID` fjernet fra `graphqlClient` — var
**grøn i begge suiter**. Først den tredje, `totalIncome → totalIncomeTYPO` i
`DASHBOARD_QUERY`, adskilte instrumenterne: dokumentet valideres mod det rigtige schema af
intet andet i repoet, fordi `useDashboardData.test.jsx:6` mocker klienten væk.

Lektien er ikke at kontrollen var forkert valgt, men at **en mutation skal vælges efter hvad
de andre instrumenter strukturelt ikke kan se** — ikke efter hvilken bug der motiverede
itemet. En bug der er rettet, er typisk også dækket.

**Trin 2's begrundelse var forkert på et punkt.** "Uden `account_id` svarer `periodOverview`
med tavse nuller" gælder REST-stien. På GraphQL-stien falder gateway'en tilbage til
`accounts[0]` — P3-25's testbruger havde **to** konti, og nullerne var et korrekt svar om den
tomme af dem (→ **P2-40**). Det blev fundet fordi mutations-kontrollen blev *grøn*, hvilket er
den ene ting man ikke kan overse.

**Trin 8 kunne ikke udføres som skrevet.** Hverken account- eller user-service eksponerer
DELETE (→ **P2-41**), så kun de fem transaktioner blev ryddet. De blev ryddet rent: 5 × 204 →
`is_deleted: true` i `transactions_v2` → `periodOverview` fra 25.000/1.629,75 til 0/0. Bruger
368 og konti 370/371 **står** i dev-stakken; det er ikke et valg, men det eneste tilgængelige
udfald. Suiten er grøn *efter* oprydningen, som trinnet krævede.

### Grænser instrumentet har, som ikke fandtes før

- **Konto-scoping kan ikke måles.** Fixturen seeder én konto pr. bruger, og med én konto er
  `accounts[0]` altid rigtigt. P2-40 er usynlig for suiten.
- **Test 2 er koblet til læsestien.** Den asserterer på et summary-kort før den måler CSP
  (bevidst — CSP på en tom side er trivielt nul violations), så en GraphQL-fejl gør *begge*
  tests røde. Læs test 1 først.
- **`docker compose restart` gendanner ikke en muteret container-fil.** Mutationen ligger i
  det writable layer; det kræver `up -d --force-recreate`. Kostede en kørsel hvor `style-src`
  stadig var muteret under `script-src`-kontrollen.
- **`compose up -d --build frontend` trækker alle ti `depends_on` med sig.** En afbrudt
  kørsel efterlod `ai-service` og `gateway-service` i `Created`, hvorefter nginx nægtede at
  starte ("host not found in upstream") — præcis som `nginx.conf`s egen kommentar forudsiger.
  Brug `--no-deps` ved gen-build af frontenden alene.

### Sideprodukt

`e2e-tests` fik `timeout-minutes: 30` (P2-38's klasse) og **port 3000 i `Wait for system`** —
loopet ventede kun på 8001-8012, så browser-suiten kunne i princippet starte mod en frontend
der ikke var oppe. `Makefile:49,91` sagde 5173 hvor porten er 3000.
