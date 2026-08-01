---
title: P3-43 — nginx som perimeter, i drift
date: 2026-07-28
status: done
backlog: [P3-43]
related:
  - ../../docs/adr/0005-nginx-as-security-perimeter.md
  - ../decisions/2026-07-28-nginx-as-perimeter.md
  - ../findings/2026-07-26-product-surface-sweep.md
  - ../plans/2026-07-28-p324-datastore-loopback-bind.md
---

# P3-43 — nginx som perimeter, i drift

## Goal

Browseren taler med **én origin**. Frontendens nginx `proxy_pass`'er per path til de ti
services på compose-netværkets interne DNS, `serviceUrls.js` bliver relativ, de 11
`CORSMiddleware` + `CORS_ORIGINS` forsvinder, og en femte regel i
`scripts/compose_check.py` gør nginx.conf til en fil der ikke kan drifte i stilhed.

Færdig når: hele app-flowet (login → transaktioner → CSV-import → budget → chat-SSE) kører
gennem `http://localhost:3000` **uden en eneste request til `localhost:800X`**, målt i
nginx' access-log frem for aflæst i koden; `/api/v1/internal/accounts/…` giver **404 fra
nginx**, ikke 401 fra account-service; og rule 5 er verificeret **rød** på hver af sine fire
assertions.

## Context

[ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md) valgte formen 2026-07-28 og
lukkede P3-24's anden halvdel. ADR'en er en beslutning uden kode; dette er koden. Den oplåser
P3-25 (CSP/HSTS ét sted) og P2-27 (`limit_req`-zone frem for `slowapi` i N services), som
begge i dag ikke har en placering at bo.

**Tre fund fra sweepet før planen ændrer opgavens form, og de står her fordi de ikke står i
ADR'en:**

1. **Der findes ingen `frontend`-service i `docker-compose.yml`.** Kun en kommentar på
   `docker-compose.yml:23`. Frontenden eksisterer som Dockerfile, som `k8s/apps/frontend.yaml`
   og som `make dev-frontend` (Vite) — men ikke i den stak vi verificerer imod. Perimeteren
   kan altså ikke *køres* i dag, og dermed heller ikke bevises. Compose-servicen er ikke en
   bekvemmelighed i denne plan; den er verifikationens forudsætning.
2. **`src/utils/apiClient.jsx:3` bærer en ellevte, udokumenteret origin:**
   `const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'`, som
   `apiClient.fetch` (`:27`) præfikser på enhver URL der ikke `startsWith('http')`. I dag er
   grenen død, fordi alle kaldsteder sender absolutte URL'er. **I samme øjeblik
   `serviceUrls.js` bliver relativ, rammer hver eneste request `localhost:8000`** — en port
   ingen service lytter på. Det er migrationens farligste enkeltlinje, og den fejler som
   "alt er nede", ikke som en URL-fejl.
3. **`GET /api/v1/users/{user_id}` er `INTERNAL_API_KEY`-vogtet** (`user-service/app/adapters/inbound/rest_api.py:67`,
   guard `:74`) — men den ligger *ikke* under et `/internal/`-segment. ADR'ens punkt 2 nævner
   kun account og categorization. Søskenden `/api/v1/users/me` gør at et præfiks-`deny` ikke
   virker. Se **Åbne valg**.

Dertil to skævheder der er billige at ramme forkert:

- **Upstream-portene er ikke browserens portnumre.** `account-service` lytter på **8003**
  (compose mapper `8004:8003`) og `ai-service` på **8004** (`8007:8004`). `proxy_pass
  http://account-service:8004` ville fejle i både compose og k8s.
- **ADR'ens ruter-tabel har tre rækker uden kaldsted:** `/api/v1/planned-transactions`,
  `/api/v1/budgets` og `/api/v1/account-groups` — nul hits i `services/frontend/src`. Se
  **Åbne valg**.

## Non-goals

- **Service-portene 8001–8012 lukkes ikke.** De bliver på `0.0.0.0`. Det er ADR-0005's punkt
  3, og det kræver først at `tests/e2e/conftest.py`s otte direkte health-polls plus de ni
  porte e2e-testene selv rammer får en vej ind. Perimeteren er en *tilføjet* vej, ikke en
  lukket dør — samme ærlighed som P3-24's "loopback er ikke sikring".
- **Ingen adfærdsændring i nogen service.** Kun `CORSMiddleware` + `CORS_ORIGINS` fjernes;
  ingen route, intet schema, ingen migration, ingen domænelogik røres.
- **Ingen security headers og ingen rate limiting.** CSP/HSTS er P3-25, `limit_req` er P2-27.
  Denne plan bygger stedet, den møblerer det ikke.
- **Ingen k8s Ingress.** k8s-halvdelen begrænser sig til at nginx.conf'en der bages ind i
  imaget bruger navne der virker begge steder. Adgang sker fortsat via port-forward, nu kun
  af frontenden.
- **Credentials røres ikke.** `guest:guest`, `xpack.security.enabled: "false"` og
  Postgres-passwords i klartekst er uændrede — ADR-0005 siger det eksplicit.
- **`ENABLE_BANKING_REDIRECT_URI` flyttes ikke.** Bankens callback til
  `localhost:8009/api/v1/bank/callback` er indgående fra Enable Bankings servere, ikke
  browser-trafik, og er registreret hos dem. Uden for perimeteren, med vilje.
- **saga-service (8011) og analytics-service (8012) får ingen location.** Browseren taler
  ikke med dem — `/api/v1/sagas` går via gateway. saga-service mister sin CORS alligevel
  (den er lige så ubrugt), analytics har aldrig haft nogen.

## Valg (afgjort 2026-07-28, før commit 1)

**A. `GET /api/v1/users/{user_id}` — accepteret på den offentlige overflade, dokumenteret.**
Guarden afviser stadig uden nøgle (`rest_api.py:19-24`), så det er ikke en bypass; det er en
S2S-rute der ligger inde bag et præfiks vi er nødt til at eksponere. Alternativet —
`location = /api/v1/users/me` før en regex-`deny` på `^/api/v1/users/[^/]+$` — blev fravalgt
fordi det køber lukningen med en **ordningsafhængighed i nginx.conf som ingen test fanger når
den brydes**, og rule 5 kan ikke udtrykke et præfiks-forbud mod noget der ikke er et præfiks.
En tavs regression i en sikkerhedsregel er dyrere end en dokumenteret, vogtet rute.
Handling: to-linjers `# P3-44`-notat over `location /api/v1/users`, og P3-44 oprettes som item
("flyt `/users/{id}` under `/api/v1/internal/`, så præfiks-reglen kan lukke den").

**B. Alle ti ruter fra ADR-tabellen kommer med fra start** — også
`/api/v1/planned-transactions`, `/api/v1/budgets` og `/api/v1/account-groups`, som i dag ikke
har et kaldsted i frontenden. Begrundelse: de tre er eksisterende, autentificerede
REST-overflader der efter al sandsynlighed får en frontend, og at tilføje dem nu koster tre
location-blokke, mens at tilføje dem senere koster en fejlsøgning der starter i browseren.
**Omkostningen skrives eksplicit:** nginx.conf beskriver dermed *den tilsigtede* offentlige
overflade, ikke den brugte — så rule 5's dækningstal er ikke et mål for hvad der faktisk
kaldes, og det må ikke læses sådan.

## Steps

### 1. [x] nginx som proxy + frontenden i compose (ingen frontend-kodeændring endnu)

Rækkefølgen er bevidst: efter dette trin kan perimeteren måles isoleret, mens frontenden
stadig kører på absolutte URL'er og alt virker som før. Ét trin, én variabel.

- `services/frontend/nginx.conf` — 13 → ~70 linjer. SPA-fallbacken bevares. Tretten eksplicitte
  `location`-blokke over ti upstreams (valg B), **ingen `location /api/`**:

  | location | upstream |
  |---|---|
  | `/api/v1/users` | `user-service:8001` |
  | `/api/v1/transactions`, `/api/v1/planned-transactions` | `transaction-service:8002` |
  | `/api/v1/monthly-budgets`, `/api/v1/budgets` | `budget-service:8003` |
  | `/api/v1/accounts`, `/api/v1/account-groups` | `account-service:8003` ← **ikke 8004** |
  | `/api/v1/categories`, `/api/v1/subcategories`, `/api/v1/rules` | `categorization-service:8005` |
  | `/api/v1/goals` | `goal-service:8006` |
  | `/api/v1/chat` | `ai-service:8004` ← **ikke 8007** |
  | `/api/v1/notifications` | `notification-service:8008` |
  | `/api/v1/bank` | `banking-service:8009` |
  | `/api/v1/graphql`, `/api/v1/sagas` | `gateway-service:8010` |

  Præfiks-match (`location /api/v1/users` uden `=` og uden trailing slash i `proxy_pass`), så
  både `/categories/` og `/categories/{id}/subcategories` rammer. Standard-sæt per blok:
  `proxy_set_header Host $host; X-Real-IP; X-Forwarded-For; X-Forwarded-Proto` — og
  **ingen** `proxy_hide_header`/whitelist af request-headers, fordi `Authorization` og
  `X-Account-ID` skal igennem (`ai-service/app/adapters/inbound/stream_api.py:34-54`).
  `/api/v1/chat` får desuden `proxy_buffering off` + `proxy_read_timeout 300s` +
  `proxy_http_version 1.1`. Servicen sender allerede `X-Accel-Buffering: no`
  (`stream_api.py:24-27`), så dette er bælte *og* seler — og timeouten er den der faktisk
  binder, da default 60s dræber en lang pipeline.
- `docker-compose.yml` — ny `frontend`-service: `build:` fra repo-roden med
  `dockerfile: services/frontend/Dockerfile`, eksplicit `image: finance-tracker-frontend`
  (rule 1/2 kræver det), `ports: ["3000:80"]`, `depends_on` på de ti. Port 3000 er valgt
  fordi `banking-service`s `FRONTEND_URL` allerede defaulter dertil
  (`banking-service/app/config.py:26`, `docker-compose.yml:727`) — bank-callbacket virker
  uden at røre en env.
- `services/frontend/vite.config.js` — `server.proxy` for de samme ti præfikser mod
  `localhost:800X` (her **er** det browser-portene, ikke container-portene). Uden dette
  brækker `make dev-frontend` i det øjeblik URL'erne bliver relative i trin 2.

**Trin 1 er udført 2026-07-28. Fire ting planen ikke forudså — alle fundet ved måling:**

1. **`proxy_set_header Host $host` brækker FastAPI's trailing-slash-redirect.** `$host`
   stripper porten, så `/api/v1/accounts` svarede
   `Location: http://127.0.0.1/api/v1/accounts/` — port 80, hvor intet lytter (curl exit 7).
   Syv af de seksten ruter giver 307, og `crudFactory` kalder accounts/goals *uden* trailing
   slash, så det ville have været en halv frontend. Fix: `$http_host`. Efter: redirecten
   bliver inden for perimeteren og lander på 401 JSON.
2. **Allowlisten holdt, men "ikke eksponeret" så ud som "virker".** `/api/v1/internal/…` og
   `/api/v1/categorize/` blev ikke proxyet — de faldt ned i SPA-fallbacken og svarede
   **200 + index.html**. Planen påstod 404. Tilføjet en `location /api/ { return 404; }`
   **deny**-backstop (ikke en proxy-catch-all, det modsatte). Det ændrer rule 5's assertion 2
   fra "ingen `/api/`-blok" til "ingen *proxyende* `/api/`-blok, og en denyende er påkrævet".
3. **nginx' default `client_max_body_size` er 1 MB** mod `CSV_MAX_BYTES` på 10 MiB. Uden
   indgreb ville CSV-import fejle med nginx' HTML-413 længe før servicens danske besked.
   Sat til 11m på transactions-locationen med vilje: servicen skal selv nå at afvise og tale.
4. **`nginx -t` fejler på et image uden kørende upstreams** — se rettelsen under Risks.
5. **Den første måling målte det forkerte instrument.** Alle seksten ruter så rigtige ud —
   og nginx' access-log havde **nul** requests. En Vite dev-server lyttede på `[::1]:3000`
   mens Docker lå på `*:3000`, og macOS foretrækker IPv6 for `localhost`, så proben ramte
   den vite-proxy jeg selv lige havde skrevet. Resultaterne var plausible og fra den forkerte
   komponent. **Brug `127.0.0.1:3000`, ikke `localhost:3000`, og bekræft i access-loggen at
   nginx overhovedet talte requesten.** Det gælder også browser-verifikationen i trin 2.

**Verifikation af trin 1 (før frontend-koden røres):** `docker compose up -d frontend`, så
`curl -i` mod alle ti præfikser gennem `:3000` → forventet svar fra rette service (401/200,
ikke 404). **Kontrol:** kommentér `/api/v1/goals`-blokken ud, genindlæs nginx → 404 fra nginx.
Sæt tilbage → svar igen. Det er beviset på at det er proxy-reglen der svarer, og ikke
SPA-fallbacken der pænt returnerer `index.html` med status 200 — den fælde er hele grunden
til at `curl -i` og ikke `curl -s` står her.

### 2. [x] Frontenden på relative URLs

- `services/frontend/src/utils/apiClient.jsx:3` — **først**. `API_BASE_URL` fjernes; præfiks-
  grenen på `:27` bliver overflødig. Dette er fundet 2 ovenfor og skal ligge i samme commit
  som relativiseringen, ellers er repoet i en tilstand hvor alt peger på `localhost:8000`.
- `services/frontend/src/config/serviceUrls.js` — de ti konstanter bliver relative
  (`'/api/v1'`, og `'/api/v1/users'` for USER — de to skæve former bevares, ellers flytter
  `/login` og `/register` sig). `VITE_*`-fallbacks droppes: de er beviseligt ikke sat nogen
  steder, så en "konfigurerbarhed" der ikke virker er værre end ingen.
- `services/frontend/.env.example:6-33` — de ti døde `VITE_*`-linjer ud.
- `services/frontend/src/utils/apiClient.test.jsx:47,59` — de to hardkodede
  `http://localhost:8001/...` bliver relative. De asserterer ikke URL'en (de rammer
  401-undtagelsen for auth-endpoints, `apiClient.jsx:48-49`), men de indkoder antagelsen.
- `services/frontend/build/` — det byggede bundle er **committet** til git
  (`build/assets/index-D14FIghg.js` indeholder de hardkodede `localhost:800X`). Genbyg i
  samme commit, så artefaktet ikke modsiger kilden. At `build/` overhovedet er committet er
  et selvstændigt problem → nyt item.

**Verifikation:** `make -C services/frontend test` (vitest). Så det rigtige flow i browseren
mod `:3000` — login, transaktionsliste, CSV-import, budget-side, chat. Aflæs
`docker compose logs frontend`: **nul** requests må gå til `localhost:800X`, og hver
API-request skal stå i nginx' access-log. Det er målingen; DevTools' network-tab er
bekræftelsen.

### 3. [x] De 11 `CORSMiddleware` + `CORS_ORIGINS` ud

Egen commit, fordi den er triviel at rulle tilbage og fordi den er den eneste der rører
backend-kode.

- 11 × `app/main.py`: `add_middleware(CORSMiddleware, …)` + importen. Filer og linjer:
  user `:27`, transaction `:31`, budget `:50`, account `:41`, categorization `:37`, goal
  `:22`, ai `:20`, notification `:20`, banking `:35`, gateway `:22`, saga `:13`.
- `CORS_ORIGINS`-feltet i de 9 settings-klasser + de 2 modul-konstanter
  (`account-service/app/config.py:97-99`, `gateway-service/app/config.py:30-32`).
- `docker-compose.yml` — 11 env-linjer (170, 213, 313, 340, 492, 566, 611, 723, 835, 936,
  1041). `k8s/configmap.yaml:8`. `example.env:40` + tre service-`example.env`.
- Docs: `README.md:462`, `services/{ai,saga,transaction,user}-service/README.md`.

**Verifikation:** ingen test asserterer på CORS-headers — `grep -rni "access-control"` over
`tests/` og `services/*/tests/` giver nul. Det betyder at suiten *ikke* kan bevise noget her,
og at verifikationen må være en måling: `curl -H 'Origin: http://evil.example' -i` mod en
service direkte **før** og **efter** commit'en. Før: `access-control-allow-origin` mangler
(origin ikke på listen) men middlewaren svarer på preflight `OPTIONS` med 200. Efter:
preflight giver 405. Det er kontrollen på at middlewaren faktisk er væk og ikke bare tavs.
Derefter samme browser-flow som trin 2 — same-origin, så CORS er irrelevant, hvilket er
pointen.

### 4. [x] Rule 5 i `scripts/compose_check.py` — nginx-drift

Filen hedder stadig `compose_check.py`, men dens docstring erklærer allerede scope som "build
hygiene", og rule 4 læser `services/*/` frem for compose. Rule 5 læser
`services/frontend/nginx.conf`. Stdlib only (CI's `repo-lint` installerer kun ruff), samme
linjeparser-stil som resten af filen.

Fire assertions, hver med en fejlmode den er set fejle på:

1. **Upstream findes.** Hver `proxy_pass http://<host>:<port>` skal svare til en
   compose-service med præcis den container-port. Fanger `account-service:8004`-fælden og
   ethvert service-navneskift.
2. **Ingen catch-all.** En `location /api/` eller `location /api/v1/`-blok er en fejl. Det er
   ADR-0005's punkt 2 som eksekverbar regel.
3. **Interne ruter er ikke publiceret.** En lille tabel af `INTERNAL_API_KEY`-vogtede
   præfikser (`/api/v1/internal/`, `/api/v1/categorize`) med kildereference; ingen location
   må matche dem. `GET /api/v1/users/{id}` kan ikke udtrykkes som præfiks og hører til valg A.
4. **Ny public service tvinger et valg.** Hver compose-service med `build:` og et
   `finance-tracker-*`-image skal enten have mindst én location eller stå på en eksplicit
   `NOT_BROWSER_FACING`-liste med begrundelse (workers, saga, analytics, frontend selv).
   Det er assertionen der fanger "ny service tilføjet uden proxy-regel" — ADR'ens punkt 4 —
   og den fejler i CI frem for i browseren.

Summary-linjen udvides med dækningstal (locations, upstreams verificeret), samme princip som
rule 4's `inspected` — en regel der tavst intet fandt er samme fejl som den den vogter imod.

**Verifikation: hver assertion køres rød hver for sig** — port ændret til 8004,
catch-all indsat, `location /api/v1/internal/` indsat, ny fake-service i compose. Fire røde,
fire grønne igen efter rollback. En vagt der aldrig er set fejle er ikke verificeret; det er
den lektie P3-40 efterlod.

### 5. [x] Verifikation samlet + docs

- `make compose-check`, `make check`, `make test-e2e` (24 forventet — e2e rammer portene
  direkte og skal være upåvirket; hvis den ikke er, har trin 3 rørt noget den ikke skulle).
- Fuld browser-gennemgang mod `:3000` inkl. **chat-SSE med timing**: log ankomsttidspunkt per
  chunk. Buffering ser ud som "alt kommer på én gang til sidst" og er usynlig i en
  succes/fejl-aflæsning.
- CI grøn; `make ci-status`.
- `docs/adr/0005-*.md` får en kort "Implementeret 2026-07-28 (P3-43)"-note med afvigelserne.
  BACKLOG.md-rækken → `done`, P3-25 og P2-27 noteres som oplåst. **To nye items oprettes:**
  P3-44 (`/api/v1/users/{id}` under `/internal/`, jf. valg A) og et item for at
  `build/`-artefaktet er committet til git. STATUS.md + session-log.
  `make notes-check`.

## Risks & rollback

| Risiko | Hvordan den opdages | Rollback |
|---|---|---|
| `apiClient`s `localhost:8000`-præfiks overses | Alt fejler på én gang, ligner "backend nede" | Trin 2 er én commit; `git revert` |
| Forkert upstream-port (account/ai) | 502 fra nginx på netop de to services | Rule 5 fanger det før commit |
| SSE buffres | Chat svarer, men i ét hug til sidst | `proxy_read_timeout` + timing-måling i trin 5 |
| CORS fjernet mens noget stadig er cross-origin | Browser-fejl på præcis den ene kald-sti | Trin 3 er isoleret; revert giver middlewaren tilbage |
| nginx bliver SPOF for API-adgang | — | Accepteret i ADR-0005: den er allerede SPOF for bundlen |
| ~~`depends_on` … nginx fejler kun på første request~~ **FORKERT, målt 2026-07-28** | — | Se note nedenfor |

**Rettelse (2026-07-28, trin 1):** rækken påstod at nginx slår upstream-navne op per
request. Det er usandt. `docker run --entrypoint nginx finance-tracker-frontend -t` giver
`[emerg] host not found in upstream "user-service"` og **exit 1** — opslaget sker ved
config-load, så en manglende upstream-container betyder at nginx slet ikke starter, ikke at
én rute fejler. `depends_on` er dermed ikke bekvemmelighed men et krav, og `restart:
unless-stopped` er det der redder en race ved kold opstart.

Hele planen er additiv indtil trin 3. Trin 1 kan stå alene (nginx virker, frontenden bruger
den bare ikke endnu), trin 1+2 kan stå uden trin 3 (CORS er så bare overflødig, ikke forkert).
Det er den egenskab der gør fem commits værd at have frem for én.

## Outcome (fill in when done)

**Udført 2026-07-28 i fem commits, `4d73b527`..`cd9b94fb`.** Formen fra ADR-0005 holdt.
ADR'en har fået en `## Implementeret`-note med de syv afvigelser; her står kun det
verifikationen viste.

### Hvad blev bevist, og hvordan

| Påstand | Bevis |
|---|---|
| Browseren taler med én origin | 0 hardkodede `localhost:80XX` i det nye bundle (11 i det gamle) |
| Hver API-request går gennem nginx | Hvert kald kvitteret i nginx' access-log, ikke aflæst i koden |
| Ruterne rammer rette service | 16 `proxy_pass`, hver verificeret mod compose af rule 5 |
| Interne ruter er ikke publiceret | `/api/v1/internal/…`, `/api/v1/categorize/`, `/api/v1/analytics/…` → **404 `text/html` fra nginx** |
| CORS-middlewaren er væk | Preflight mod alle 11 porte: 200 + ACAO før, **405 uden headers** efter |
| CSV-import virker gennem perimeteren | `import-csv` → 200, `{"imported":6}`, transaktionerne læsbare bagefter |
| Servicen, ikke nginx, afviser store filer | 10,5 MiB-fil → **servicens danske 413**, ikke nginx' HTML-413 |
| CQRS-læsesiden virker same-origin | GraphQL `financialOverview` → rigtig aggregeret data (700 / 5740,08) |
| SSE buffres ikke | 9 chunks spredt over **145s**, ikke ét hug |
| `proxy_read_timeout 300s` binder | Strømmen levede 162s — defaultens 60s ville have dræbt den |
| E2E er upåvirket | `make test-e2e`: **24 passed**, fordi den rammer portene direkte |
| Rule 5 kan fejle | 11 mutationer, alle røde med den forventede besked, grøn igen efter rollback |
| Det målte er det shippede | CI **SUCCESS på `ee1a968b`** ([run 30372244517](https://github.com/Jothom2912/Finance-Tracker/actions/runs/30372244517)) — rule 5 kører også dér, via `ci.yml:53` |

Sidste række er ikke pynt. Før push rapporterede `make ci-status` **SUCCESS** — på
`abbc43f6`, ADR-commit'en fra *før* al kode i denne plan. Det er bogstaveligt den fejlklasse
rule 5 findes for: en grøn kørsel der intet siger om det der shippede. Aflæs altid hvilken
SHA tallet gælder.

### Hvad IKKE blev bevist — og det er planens eneste åbne ende

**Chat-SSE'ens *pipeline* kunne ikke køres end-to-end.** `qwen3:8b` bliver OOM-dræbt på denne
maskines 7,8 GB Docker-hukommelse (`llama-server ... signal: killed`), så begge forsøg endte i
`event: error`. **Kontrolleret at det ikke er perimeteren:** samme request direkte mod
`:8007`, uden nginx, fejler identisk. → **P3-46**.

Det betyder at Goal-sætningens "login → transaktioner → CSV-import → budget → chat-SSE" er
opfyldt for de fire første og for chat-SSE'ens *transport*, men ikke for dens indhold. Den
skelnen er værd at holde fast på: transporten var det perimeteren kunne brække, og den er
målt på det der binder (buffering og timeout). Pipelinen er en anden fejl, i en anden
komponent, som denne plan hverken forbedrede eller forværrede.

**Browser-gennemgangen blev gjort på HTTP-niveau, ikke i en rigtig browser.** Der er ingen
Playwright/Puppeteer i repoet, så DevTools' network-tab er stadig ubekræftet. Sammen med
bundle-grep'et fra trin 2 (0 hits på `localhost:80XX`) og access-loggen fra hvert kald dækker
det samme påstand fra to sider, men det er ikke det samme som at have set det.

### Fire ting planen tog fejl i

1. **"Før: preflight `OPTIONS` med 200" (trin 3).** Starlette svarer **400** på en ikke-tilladt
   origin. Havde evil-rækken været diskriminatoren, ville 400→405 have set ud som et resultat
   uden at være det. Diskriminatoren var rækken med den *tilladte* origin, fordi kun den bar
   ACAO.
2. **`services/frontend/build/` er ikke committet** — den er gitignored
   (`services/frontend/.gitignore:12`). Trin 2's genbygningsopgave og det tilhørende
   follow-up-item bortfaldt.
3. **Trin 3's "9 settings-klasser + 2 modul-konstanter" var rigtigt, men ufuldstændigt:** syv
   `main.py` stod tilbage med et nu ubrugt `from app.config import settings`. Fail-fast på
   `JWT_SECRET` bevares, fordi `app.config` importeres transitivt af routere/dependencies i
   alle syv — verificeret, ikke antaget.
4. **Rule 5's fire assertions blev syv fejlmoder.** De tre ekstra kom af at skrive kontrollerne
   *før* jeg troede reglen var færdig: en upstream uden `ports:` og en `location` med modifier
   er **uafgørlige**, ikke bestående, og `NOT_BROWSER_FACING` skulle kunne modsiges af
   nginx.conf. En regel der springer en assertion rapporterer succes for noget den ikke har
   læst — samme fejlklasse som resten af filen vogter imod.

### Oplåst

**P3-25** (CSP/HSTS) og **P2-27** (`limit_req` frem for `slowapi` i N services) har nu et sted
at bo: perimeterens `server`-blok. Begge rækker er noteret i BACKLOG.

### Nye items

- **P3-44** — flyt `/api/v1/users/{id}` under `/internal/` (valg A's gæld).
- **P3-45** — nginx cacher upstream-IP'er ved config-load; byttet ved `resolver` er skrevet ned.
- **P3-46** — `qwen3:8b` OOM-dræbes; blokerer end-to-end-verifikation af chat.

