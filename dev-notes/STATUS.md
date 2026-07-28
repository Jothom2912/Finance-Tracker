# Status — 2026-07-28 (efter P2-39: repoet har et browser-lag)

Where the work stands right now. **Read this first**; it exists so a session does not start
by guessing which of 32 plans is live. Update it when the active plan changes, an item
finishes, or a session ends — a stale STATUS.md is worse than none.

Everything here is derivable from the backlog and plan statuses; this file is a shortcut,
not a second source of truth. If it disagrees with `backlog/BACKLOG.md`, the backlog wins.

## Active

**Intet aktivt item.** P2-39 er shippet; næste er et valg mellem de items den afdækkede
(P2-40, P2-41) og de allerede kendte (P2-38, P3-41, P3-44, P3-46).

Sidst shippet: **P2-39 — browser-automatisering som ejet instrument** (2026-07-28), syv commits
`35f2e047`..`9ea54d38`. Repoet har nu et **tredje instrument**: 3 Playwright-tests i
`services/frontend/e2e/` der driver det byggede image bag perimeteren på `127.0.0.1:3000`, som
hård gate i `e2e-tests`. `make test-browser` lokalt, ~16 s.
[Plan + Outcome](plans/2026-07-28-p239-browser-automation.md#outcome) ·
[decision](decisions/2026-07-28-browser-automation-instrument.md).

**Det vigtigste udbytte er ikke suiten, men hvad mutations-kontrollen afslørede — to gange ved
at blive GRØN.** Planens eget færdig-kriterium holdt ikke: P1-16 genindført gør *begge* suiter
røde, fordi bug'en fik sin egen jsdom-regressionstest da den blev rettet. Kontrollen der
adskiller instrumenterne er i stedet `totalIncome → totalIncomeTYPO` i `DASHBOARD_QUERY`:
**`npm test` 346 passed, browser-suiten 2 failed** — GraphQL-dokumentet valideres mod det
rigtige schema af intet andet i repoet. **Reglen der bliver:** vælg mutationen efter hvad de
andre instrumenter *strukturelt* ikke kan se, ikke efter hvilken bug der motiverede itemet. En
rettet bug er typisk også dækket.

**Og en diagnose vi har troet på siden P3-25 var forkert.** "Uden `X-Account-ID` svarer
`periodOverview` med tavse nuller" gælder REST-stien. På GraphQL-stien falder gateway'en tilbage
til `accounts[0]` (`gateway/auth.py:99`), og P3-25's testbruger havde **to** konti — nullerne var
et *korrekt svar om den tomme konto*. En flerkonto-bruger får altså en anden kontos data
præsenteret som den valgte, uden en fejl (→ **P2-40**). Det blev fundet fordi mutationen blev
grøn, hvilket er den ene ting man ikke kan overse.

**C2 er lukket med et tal:** `style-src` uden `'unsafe-inline'` → **1 violation**
(`style-src-elem`/inline) ved dialog-klikket, **0** på `/dashboard`. Direktivet er nødvendigt, og
præcis kun af den grund `nginx.conf` angiver. Klikket P3-25 ikke kunne lave, er nu checket ind.

**Grænser suiten har — læs dem før den bruges som dækning:** den seeder **én** konto pr. bruger,
så konto-scoping (P2-40) er usynlig for den. Test 2 asserterer på et summary-kort før den måler
CSP, så en fejl i læsestien gør *begge* tests røde — læs test 1 først. Og grøn-på-ingenting ramte
inde i instrumentet selv: fixturens egen vagt var grøn under `script-src 'none'`, altså på en app
uden en linje kørende JS, indtil den fik en assertion om at appen mountede.

**Første CI-kørsel var rød, og fundet var ægte: i CI kan banking-service ikke læse sin PEM, så
`/bank/connections` svarer 500 ved hver dashboard-load.** Lukket i **to** forsøg, og begge fejl
i min egen diagnose er værd at kende: (1) servicen *dør ikke ved boot* som jeg først skrev —
`EnableBankingClient` konstrueres per request, og `/health` var 200 hele vejen, hvilket min egen
8009-kontrol beviste ved at **bestå**; et liveness-probe kan ikke se en brudt afhængighed. (2)
`openssl genrsa` alene var ikke nok: den skriver mode 600 ejet af runneren, mens containeren kører
som `uid=10001`, så fejlen flyttede sig fra `IsADirectoryError` til `PermissionError`. `chmod 644`
lukkede den. Den åbne del (500 hvor konventionen er 503) er **P2-42**.
[Finding](findings/2026-07-28-banking-service-dead-in-ci.md).

**Sideprodukt:** `e2e-tests` fik `timeout-minutes: 30` og **port 3000 i `Wait for system`**
(loopet ventede kun på 8001-8012, så suiten kunne starte mod en frontend der ikke var oppe).
`Makefile` sagde 5173 hvor porten er 3000.

**Trin 8 stødte på en mur der blev et item:** hverken account- eller user-service eksponerer
DELETE, og `Account` har ingen `is_deleted`-kolonne (→ **P2-41**). Kun P3-25's fem transaktioner
blev ryddet — rent, via API'et: 5 × 204 → `is_deleted: true` i `transactions_v2` →
`periodOverview` fra 25.000/1.629,75 til **0/0**. Bruger `csp_probe` (368) og konti 370/371
**står** i dev-stakken, fordi der ikke findes en vej ud.

### Forrige: P3-25 + P2-27 + P1-16

Sidst shippet: **P3-25 + P2-27, plus P1-16 som utilsigtet udbytte** (2026-07-28), fire commits
`38634dca`..`474b9643`. Perimeteren har nu fire security headers (med `always`, så også på
deny-backstoppens 404) og to `limit_req`-zoner på login og register.
[Plan + Outcome](plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md#outcome) ·
[session-log](sessions/2026-07-28-p325-p227-perimeter-hardening.md).

**Læs dette før noget andet, fordi det ændrer hvad vi tror en verifikation er værd: P3-43
brækkede hele GraphQL-læsestien i browseren, og det stod på master i nogle timer.**
`graphql-request` kalder `new URL(url)` uden base, så den relative sti fra `c0418646` kastede
`TypeError: Invalid URL` — dashboard, transaktioner og kategorier viste
`Fejl: Failed to construct 'URL': Invalid URL` i stedet for data. Lukket af **P1-16**
(`68dc3db0`) med en absolut URL bygget fra `window.location.origin` i `graphqlClient.jsx`;
`serviceUrls.js` er stadig relativ, så ADR-0005 er uændret.
[Finding](findings/2026-07-28-graphql-client-rejects-relative-url.md).

**Kæden af tavsheder er lektien, ikke bug'en.** P3-43 verificerede GraphQL med `curl`, og STATUS
sagde *"GraphQL leverer rigtig aggregeret data same-origin"* — sandt **om transporten**. nginx
proxyer korrekt; `curl` kører bare ikke klienten. Og de 344 frontend-tests er blinde ved
konstruktion, fordi `graphqlClient.test.jsx:12` mocker `GraphQLClient` væk — målt, ikke påstået:
med regressionen genindført fejler **kun de to nye tests**, mens de fire mockede bliver grønne.
**Fundet kom fra en kontrol i et urelateret item:** CSP'en kunne kun verificeres ved at *drive*
appen i en rigtig browser-engine, og det krævede en autentificeret session. Ingen leden fandt
den.

**Verifikationen der tæller for de to items:** headerne sidder på 200, **404 og et proxyet 422**
(de to sidste er `always`-beviset, da ingen af dem er på nginx' default-hvidliste). CSP'en er
bevist *håndhævet* og ikke kun leveret — kontrol med `script-src 'none'` gav violation **og** en
app der ikke mountede. Rate limiten: 6 igennem på frisk zone, verificeret rød uden `limit_req`
(20/20), og `/users/me` + `/transactions/` urørte (20/20 × 200).

**To ting der ikke er som planen sagde.** (1) `'unsafe-inline'` på `style-src` er nødvendig, men
**ikke** på grund af de 35 `style={{}}` — React bruger CSSOM, og CSP rører ikke CSSOM (målt: 24
style-attributter under `style-src 'self'`, nul violations). Det er radix' scroll-lock der tvinger
den. Rettet i `e377a420`. (2) Planen foreskrev **én** rate-limit-zone; målingen viste at fælles
zone lod register-spam spærre alles login, så der er **to**.

**Åbne ender, med vilje ikke skjult:** `limit_req` er **omgåelig** — 20 requests direkte mod
`:8001` gav nul 429, fordi portene stadig er på `0.0.0.0` (ADR-0005 punkt 3), og vores egen
`tests/e2e/` er beviset, da den er upåvirket. Zonen er desuden per-IP i *form* og **én global
bucket i praksis**, fordi `$remote_addr` er Docker-gatewayen for al host-trafik (per-IP bevist
via en sibling-container). Og C2-kontrollen manglede sin app-nære form, fordi et
dialog-klik ikke kunne automatiseres — **lukket af P2-39**: 1 violation med `style-src` uden
`'unsafe-inline'`, 0 på `/dashboard`.

Den før det: **P3-43 — nginx som perimeter, i drift** (2026-07-28), fem commits
`4d73b527`..`cd9b94fb`. Browseren taler med én origin: 16 eksplicitte `proxy_pass`-locations
plus en **denyende** `location /api/ { return 404; }`, frontenden på relative URLs, de 11
`CORSMiddleware` + `CORS_ORIGINS` væk, og rule 5 i `scripts/compose_check.py` vogter nginx.conf
mod drift. Oplåste **P3-25** og **P2-27**, som begge lukkede 2026-07-28 (se ovenfor).

**Det gennemgående fund, og grunden til at det står her og ikke kun i session-loggen:** hvert
af de fem trin havde en måling der modsagde planen, og alle fem handlede om at noget *så ud*
som om det virkede. Ikke-proxyede ruter svarede **200 + index.html** fra SPA-fallbacken (deraf
deny-backstoppen). Den første rute-måling ramte en Vite dev-server på `[::1]:3000` frem for
nginx, og gav plausible svar fra den forkerte komponent — **brug `127.0.0.1:3000`, og bekræft i
access-loggen at nginx talte requesten.** Frontendens 344 tests bestod stadig med URL-fejlen
genindført som kontrol, fordi de mocker `fetch`. Og planens forudsagte preflight-200 var i
virkeligheden 400, så den forkerte række ville have været diskriminator.

**Verifikationen der tæller:** preflight mod alle 11 porte gik fra 200 + `access-control-allow-origin`
til **405 uden headers**; `/api/v1/internal/…` og `/api/v1/categorize/` giver nu **404 fra
nginx**; en 10,5 MiB CSV får **servicens** danske 413, ikke nginx' HTML-413; ~~GraphQL leverer
rigtig aggregeret data same-origin~~ (**dette var kun sandt om transporten** — klienten var
brækket, se P1-16 ovenfor); `make test-e2e` er **24 grønne**, fordi den rammer portene
direkte og skulle være upåvirket. Rule 5 er kørt **rød på 11 mutationer** hver for sig.

**Åben ende, med vilje ikke skjult:** chat-SSE'ens *pipeline* kunne ikke køres end-to-end —
`qwen3:8b` OOM-dræbes på 7,8 GB Docker-hukommelse (→ **P3-46**). Kontrolleret at det ikke er
perimeteren: samme request direkte mod `:8007` fejler identisk. SSE'ens *transport* er derimod
målt, og på det der binder: 145s spredning mellem chunks (buffering ville give ~0) og en strøm
der levede 162s, forbi defaultens 60s `proxy_read_timeout`. Browser-gennemgangen blev gjort på
HTTP-niveau; der er ingen Playwright i repoet, så DevTools er ubekræftet.

Den før det: **P3-24's ADR-halvdel** (2026-07-28) —
[ADR-0005](../docs/adr/0005-nginx-as-security-perimeter.md): **frontendens nginx er
perimeteren, ikke gateway-service**, som forbliver CQRS-læsesiden. Ingen kode; beslutning +
[decision-note](decisions/2026-07-28-nginx-as-perimeter.md) + P3-43 som implementeringsitem.

**Fundet der omformede beslutningen:** spørgsmålet var ikke "hvordan sikrer vi produktion",
for **der findes ikke en deployment hvor en perimeter ville være nåelig.** k8s har 30
ClusterIP-Services og hverken Ingress, NodePort eller LoadBalancer; adgang sker via
`kubectl port-forward`, som gendanner de samme localhost-origins. Og frontendens `VITE_*`-vars
er ikke sat nogen steder, så de hardcodede `localhost:800X` er dem der bygges ind i imaget.
ADR'en forpligter altså en *form* mens der intet er at bryde.

**Gateway-alternativet blev afvist på arkitektur, ikke pris:** den ville få en Python-hop foran
hver write og gøre CQRS-læsesiden til skrive-chokepunkt. Multi-origin blev afvist fordi det
ikke er gratis — det koster allerede 11 `CORSMiddleware` i sync, og prisen er løbende mens
besparelsen er engangs.

Den før det: **P3-24, datastore-halvdelen** (2026-07-28) — de 14 datastore-mappings i compose
binder `127.0.0.1` i stedet for `0.0.0.0`. Én commit, `5ea37f0d`, kun `docker-compose.yml`.
Ingen kode, ingen migration.

**Eksponeringen var reel og blev målt før indgrebet**, ikke aflæst i compose-filen: alle 14
porte svarede fra LAN-IP'en, ES gav `transactions_v2` **642 docs** + `accounts_v1` **292** uden
auth, og RabbitMQ-mgmt gav fuld admin på `guest:guest`. Efter: **0/14 fra LAN, 14/14 på
loopback**. Kontrol kørt — ES alene rullet tilbage til `0.0.0.0`, de 642 docs igen læsbare fra
LAN, sat tilbage → refused.

**Backloggens "no downside" var kun sandt for det ene af to indgreb.** At *slette* `ports:`
ville rive syv legitime host-side-forbrugere over, heraf én i CI
(`test_budget_month_closed_e2e.py` publicerer via mgmt-API'et på 15672). Truslen fundet
navngiver er LAN-rækkevidde, så loopback-bind rammer egenskaben uden den omkostning. Rubrikken
i BACKLOG.md er rettet.

**CI grøn på `baeb663f`** (run `30360964811`), alle 19 jobs. E2E gav 24 passed, og de tre
`test_budget_month_closed`-tests er navngivet PASSED i loggen — det er kvitteringen på
valget: den forbruger der bruger mgmt-API'et på 15672 kører i CI og virker med
loopback-binding.

Credentials er urørte: angrebsfladen er flyttet fra "alle på LAN'et" til "alt på maskinen" —
ikke lukket. (ADR-halvdelen lukkede samme dag, se ovenfor.)
[Plan + Outcome](plans/2026-07-28-p324-datastore-loopback-bind.md#outcome) ·
[session-log](sessions/2026-07-28-p324-datastore-loopback.md).

Den før det: **P2-29** (2026-07-28) — byte-, række- og transportgrænse på `/import-csv`.
Fem commits: `555ffd5e` (`CSV_MAX_BYTES`/`CSV_MAX_ROWS`, handler-guard før `.read()`,
rækkegrænse i `ParsedCSVResult.add_row` så de tre parsere deler én implementation),
`7f4c35ac` (`Content-Length`-middleware), `d0661ad1` (12 tests — endpointets **første**
adapter-dækning, integration 69 → 81), `4621ac2a` (frontend pre-flight),
`880138f7` (alembics `fileConfig()` slukkede appens loggere).
Ingen migration, intet schema rørt.

**OOM'en var virkelig, og det blev målt som kontrol.** `mem_limit: 512m` (k8s' tal) plus
`CSV_MAX_BYTES` hævet via env — samme image, én variabel ændret — gav
`OOMKilled=true, ExitCode=137` på en 150 MB upload. Med guarden på: 413 på 3 ms, RSS uændret
(82,26 → 82,41 MiB), container oppe. Hver guard er bevist i stand til at blive rød:
handler-guard fjernet → 2 røde, middleware → 1, rækkegrænse → 1.

**Planens egen disk-måling var et forkert instrument.** `du -sh /tmp` viste 4 KB mens 150 MB var
i luften, fordi `tempfile` bruger `O_TMPFILE` (unlinked, ingen directory-entry). `df -k` pollet
under uploaden: Content-Length-stien 0 MB, chunked-stien **137 MB**. Det accepterede chunked-hul
er dermed kvantificeret frem for kun navngivet.
[Plan + Outcome](plans/2026-07-28-p229-csv-upload-guards.md#outcome) ·
[session-log](sessions/2026-07-28-p229-csv-upload-guards.md).

**CI grøn på `880138f7`** (run `30358915496`) — altså på alle fem commits. Den femte var
nødvendig for at komme dertil: suiten var rød i CI på to push og grøn når testklassen kørte
alene. `fileConfig()` defaulter til `disable_existing_loggers=True`, så hver logger der fandtes
da migrationen kørte blev `.disabled = True` — og `categorized_consumer` importeres ved
collection, altså før `_migrated_db`. Adfærden var korrekt hele tiden; **kun sporet forsvandt**,
og testen asserterer på sporet. Import-rækkefølgen afgjorde det, ikke soft-delete-koden.

Den før det: **P2-25 + P3-37** (2026-07-28) — soft-delete på `transactions`. Fem commits:
`762e6c5b` (migration 013: `deleted_at` + det partielle external_id-index narrowet med
`AND deleted_at IS NULL`), `4deb9dac` (prædikater på alle læse-stier og begge dedup-queries;
`delete` stempler i stedet for at fjerne), `9a578fac` (ni integrationstests),
`3df1d778` (consumerens tredje gren), `2b59e77f` (`cleanup_pg_duplicates.py`).
P3-37 var aldrig et selvstændigt item — migrationen alene har ingen værdi, consumer-grenen alene
er umulig at skrive.

**Blast radius var mindre end frygtet, og det blev målt:** ES og analytics blev ikke rørt, fordi
projektionen allerede satte `is_deleted: true` og `_base_filters` allerede filtrerede på det.
Ændringen er transaction-service plus ét maintenance-script.

**Kontrollen korrigerede planens præmis.** Planen tilskrev DLQ-fixet consumer-grenen; med grenen
fjernet, men soft-delete på plads, fejler kun én af dens fire tests, fordi rækken nu *findes* og
der aldrig backes off. Soft-delete alene lukker DLQ-stien; grenen forhindrer at en tombstone får
sine kategoriseringsfelter overskrevet. Samme greb på repo-niveau: med prædikaterne fjernet fejler
7 af de 9 soft-delete-integrationstests.

Live-verificeret på fuld compose-stak: kolonnen og indexet aflæst i `\d transactions`
(ikke kun exit-kode 0), `total_count` faldt med præcis 1, `/analytics/overview` med præcis
rækkens beløb (500,00 → 0,00), ES-dokumentet `is_deleted: true`, re-import gav et nyt id, og
DLQ-reproduktionen kørt **med kontrol**: den slettede tx acker stille (DLQ 2 → 2, én INFO-linje),
mens et id der aldrig har eksisteret stadig backer off og lander i DLQ'en (2 → 3).
`make test-e2e` 24 passed.
[Plan](plans/2026-07-28-p225-transaction-soft-delete.md) ·
[decision](decisions/2026-07-28-transaction-soft-delete.md).

Den før det: **P3-23** (2026-07-28) — banking-service på uv + pyproject, med lockfile,
dev/runtime-split og på typecheck-gaten (**9 af 12**; install-sti **11 af 12**). Fire commits:
`6e9c8bda` (pyproject + `uv.lock`, `requirements.txt` slettet, `python-jose` ud af runtime),
`6a998bc0` (Dockerfile på `uv sync --frozen --no-dev`), `0fd25d59` (mypy-gaten), + docs.
Udbyttet gentog P2-31's mønster: de 31 første mypy-fejl var **fire allerede kendte kontrakt-items**
(P2-32/33/35/36) plus fem ægte annotations-fejl — ingen nye bugs.
Runtime-verificeret lokalt: `app.main` + alle fire worker-moduler importerer under imagets
fastapi 0.140.7, container op, alembic kørt, alle fire workers forbundet til RabbitMQ.
CI grøn på `e8865dcb` (run `30313411120`). Verificeret som **kontrol** via
`make verify-typecheck-gate`: **9 gated / 3 not gated**, og banking rapporterer `notice=no` —
altså at mypy faktisk kørte, ikke at steppet blev sprunget over.
[Plan + Outcome](plans/2026-07-28-p323-banking-uv-pyproject.md#outcome) ·
[session-log](sessions/2026-07-28-p323-banking-uv-pyproject.md).

Den før det: **P2-37** (2026-07-28) — budget-services image installerer fra `uv.lock` som de 9
andre, så tests, mypy og container læser samme fil. Tre commits: `560cd54a` (Dockerfile +
`requirements.txt` slettet), `8d7c8f59` (tre døde `freeze:`-targets), `18bd5fc8` (vagt i
`scripts/compose_check.py` mod at en service igen har begge filer, verificeret rød på både
transaction og budget). CI grøn på `d555f20e` — alle **19** jobs, inkl. E2E og det omdøbte
`Build-hygiene check`-step, som er rule 4's første kørsel i CI (run `30311338979`).
Runtime-beviset er lokalt: container op, alembic kørt, `app.main` importeret under fastapi
0.136.3 med alle tre 204-ruter, og alle tre workers oppe.
[Plan + Outcome](plans/2026-07-28-p237-budget-single-install-path.md#outcome) ·
[session-log](sessions/2026-07-28-p237-single-install-path.md).

Den før det: **P2-31** (2026-07-27) — mypy som hård gate på **8 af 12** services, styret af
`TYPECHECK_SERVICES` i `ci.yml`. CI grøn på `36428508` (run `30308332057`). Verificeret som
kontrol via `make verify-typecheck-gate`.
[Plan + Outcome](plans/2026-07-27-p231-static-typecheck-gate.md#outcome) ·
[session-log](sessions/2026-07-27-p231-typecheck-gate.md). Udbyttet var **usande kontrakter, ikke
typefejl** — det er derfor de seks items den affødte (P2-32…P2-37) er kontrakt-items og ikke
oprydning.

## Next up

- **P2-21** — k8s manifest drift: 6 workloads + 1 DB i compose har ingen manifest, så
  `apply -k` taber notification-feeden og den automatiske ADR-0003-kæde i stilhed.
  CI-check-halvdelen er nu billigere: `scripts/compose_check.py` er stedet at lægge
  compose-vs-kustomization-diffen. Filen har efter P3-43 **fem** regler og læser compose,
  `services/*/` og `services/frontend/nginx.conf` — så præcedensen for en sjette er solid, men
  omdøbningen er også optjent for anden gang. Bemærk at "build hygiene" ikke længere dækker
  scopet præcist: rule 5 er en sikkerhedsregel, ikke en build-regel, og de deler kun
  fejlmoden *en grøn kørsel der intet beviste*. Vælg navnet efter fejlmoden, ikke emnet.
- ~~Browser-automatisering fortjener en beslutning~~ — **truffet 2026-07-28 som P2-39**, se
  **Active**. Har nu ID, decision-note og plan.
- **P3-47** — en `location` med eget `add_header` fjerner tavst perimeterens fire security
  headers i den blok. Ikke akut i dag (filen har ingen andre `add_header`), men **P3-28 er det
  item der udløser det**, så de to hører sammen i rækkefølge.
- **P2-28** — taxonomy write auth kræver stadig en beslutning om et rolle-begreb, som ikke
  findes nogen steder i kodebasen.
- **P3-46** — `qwen3:8b` OOM-dræbes når stakken kører, så ai-service kan ikke verificeres
  end-to-end lokalt. Ikke et produktfejl, men det blokerer for *evidens* om chat, og det er
  derfor det bør ligge tidligt: (a) hæv Docker-memory er gratis at prøve først.

Ikke akut, selvom titlen lyder sådan: **P2-36** (`x-retry-count` → uendelig redelivery) — hver
writer i repoet sætter en `int`, så `str`-grenen nås ikke af vores egne republishes. Hærdning.

**P2-32/33/35/36 har nu hver et fodfæste i banking.** P3-23 efterlod dem som
`# type: ignore[...]  # P2-3x` (grep dem frem med `grep -rn 'ignore\[' services/banking-service/app`).
`warn_unused_ignores` er slået til, så **den service der fejler når et af de fire items fixes,
er banking** — det er ikke en regression, det er kvitteringen. Fjern ignoren i samme commit.

## Open findings worth knowing before you touch anything

| Finding | Severity | Scheduled as |
|---|---|---|
| [product-surface sweep](findings/2026-07-26-product-surface-sweep.md) | HIGH | P2-26..29 (**29 lukket**), P3-24..34 (**24 lukket** → P3-43), F2-08..13 |
| [CI-job kan hænge uopdaget](findings/2026-07-28-ci-job-can-hang-undetected.md) | MEDIUM | P2-38 |
| [k8s manifest drift](findings/2026-07-25-k8s-manifest-drift.md) | MEDIUM | P2-21 |
| [outbox-port erklærer fremmed entitet](findings/2026-07-27-outbox-port-declares-foreign-entity.md) | MEDIUM | P2-32 (7 services) |
| [Optional id skjuler upersisteret entitet](findings/2026-07-27-optional-id-hides-unpersisted-entity.md) | MEDIUM | P2-35 |
| [goal: `Goal` har to runtime-typer](findings/2026-07-27-goal-entity-two-runtime-types.md) | MEDIUM | P2-34 (blokerer goal for gaten) |
| [x-retry-count læst fem måder](findings/2026-07-27-retry-header-read-five-ways.md) | MEDIUM | P2-36 (ikke live i dag) |
| [INTERNAL_API_KEY optional-men-obligatorisk](findings/2026-07-27-internal-api-key-optional-but-mandatory.md) | LOW | P2-33 (6 services) |
| [graphql-request afviser relativ URL](findings/2026-07-28-graphql-client-rejects-relative-url.md) | HIGH | P1-16 (**lukket 2026-07-28**) — men lektien om `curl`-verifikation står stadig |
| [131 bare mocks uden `spec`](findings/2026-07-27-sync-trigger-double-value.md) | MEDIUM | P3-41 — nu det største usikrede areal, da `tests/` er uden for mypy-scope. **P1-16 viste at mocks også skjuler regressioner i frontenden**, ikke kun kontraktbrud i services |
| [worker migration ordering](findings/2026-07-25-worker-migration-ordering.md) | LOW | P3-17 |
| [eval seed writes to prod index](findings/2026-07-26-eval-seed-writes-to-prod-index.md) | LOW | P3-21 |
| [non-UUID saga_id poison](findings/2026-07-25-saga-reply-non-uuid-poison.md) | LOW | P3-19 |

## Standing traps

- `account-service` is pip-based with no venv: `make test` / `make lint` fail locally regardless
  of the code, and repo-wide `make lint`/`make check` abort on it before reaching the other
  eleven. See P3-39 (banking's half closed by P3-23; its suite now runs locally, 68 passed).
- Never pipe a verification command through `tail`/`head` — the pipeline's exit code is the
  last command's, so `check | tail && git commit` commits on a failing check. **Ramte igen
  2026-07-28** i P3-24's kontrol: `curl … | head -3 && echo "kontrol rød"` printede beskeden
  mens curl intet returnerede, fordi ES ikke var startet endnu. En kontrol var ét sekund fra at
  blive noteret som bestået uden at være kørt. Fælden overlever at være skrevet ned — læs
  `rc=$?` eksplicit i stedet.
- **Genskaber du datastore-containere under kørende app-services, ligner det en regression.**
  Set i P3-24: `docker compose up -d postgres-*` gav 7 e2e-fejl med
  `InterfaceError: connection is closed`, fordi asyncpg-poolene holdt døde forbindelser.
  `docker compose restart` af app-laget → 24 passed. Genstart app-services efter datastores,
  før du konkluderer noget om ændringen.
- **Datastores er kun loopback-bundne, ikke sikrede** (P3-24). `guest:guest`,
  `xpack.security.enabled: "false"` og Postgres-passwords i klartekst i compose er uændrede,
  og enhver container når stadig hosten via `host.docker.internal` — verificeret. Antag ikke
  at porten er lukningen.
- **En CI-kørsel der står på `in_progress` kan være hængt, ikke langsom** — og intet i repoet
  afgør hvilket. Set 2026-07-28: analytics' `Run tests` sad 836 s hvor baselinen er 36 s, og
  ville have siddet i 360 min (ingen `timeout-minutes`, ingen wait-timeout på ES-fixturen →
  P2-38). **Logs udleveres først når jobbet slutter**, så diagnosen kræver at man aflyser
  først. Fremgangsmåden der virkede: sammenlign jobbets varighed med de sidste grønne kørsler
  (`gh run list --status success` + `gh run view --json jobs`), aflys for at få loggen, og
  genkør *samme commit* — bliver den grøn uden kodeændring, er det infrastruktur og ikke dig.
- **En `curl`-verifikation beviser transporten, ikke klienten.** P3-43 verificerede GraphQL
  same-origin med `curl` og fik et sandt svar; klienten var alligevel brækket for hver bruger
  (P1-16). Rammer alt hvor et bibliotek står mellem appen og HTTP — `graphql-request` konstruerer
  selv en `URL`, `fetch` gør ikke. **Spørg hvad der kører i browseren, som `curl` ikke kører.**
- **En mocket afhængighed kan være selve blindheden.** `graphqlClient.test.jsx` mocker
  `GraphQLClient` for at teste 401-interceptoren — legitimt — men det var derfor 344 grønne tests
  ikke kunne se P1-16. Målt: med regressionen genindført fejler kun de to tests der *ikke* mocker.
  Når en test mocker det den skal bevise noget om, hører der en søskende-test uden mocket til.
- **En fejlet kommando kan have haft bivirkninger inden den fejlede.** P2-27's første
  rate-limit-måling viste 2 igennem i stedet for 6, fordi et `declare -A`-forsøg (virker ikke i
  zsh) havde afsendt requests før det fejlede og drænet bucket'en. Beslægtet med pipe-fælden:
  **etablér tilstanden på ny før en måling tolkes.**
- **Workers are still second-class in compose**: P3-40 fixed the *image* half, but P3-17 is
  open — workers override `command:` and so skip the migrations that run in the API's `CMD`.
- **En grøn `make check` er stadig ikke et løfte om at containeren starter** — men grunden er
  ændret. Den *todelte* årsag (budgets image `pip install`ede `requirements.txt` mens tests læste
  `uv.lock`) er væk med P2-37, og `make compose-check` fejler nu hvis den kommer tilbage. Tilbage
  står at `check` er statisk: den importerer ikke `app.main` under imagets versioner. `account`
  har desuden stadig ingen lockfile, så for *den* er der ikke engang en fil at være enig med
  (P3-01). Det billige modtræk, brugt i både P2-37 og P3-23:
  `docker run --rm <image> python -c "import app.main"` plus samme import af hvert worker-modul.
- **`tests/` er ikke typechecket** på nogen af de 9 gatede services (`packages = ["app"]`), og
  de 3 udenfor er slet ikke dækket — antag ikke at en typefejl er fanget i goal, account
  eller gateway.
- **`make notes-check` verificerer mekanik, ikke sandhed.** Den var grøn mens denne fil sagde
  at P2-31 ikke var påbegyndt. Kandidater til at lukke det hul står i
  [session-loggen](sessions/2026-07-27-p115-p226-and-notes-infra.md) under Open ends.
- `make ci-status` for the current branch's CI; `make notes-check` before committing notes;
  `make compose-check` before committing `docker-compose.yml` **or adding a dependency file to a
  service** — den bærer nu to regler (worker-image-deling + én install-sti per service).
