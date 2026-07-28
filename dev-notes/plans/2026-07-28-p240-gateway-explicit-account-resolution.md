---
title: P2-40 — gateway'ens accounts[0]-fallback: vælg eksplicit eller fejl ærligt
date: 2026-07-28
status: done
backlog-items: [P2-40]
related:
  - ../findings/2026-07-28-gateway-falls-back-to-first-account.md
  - ../findings/2026-07-27-gateway-default-account-307.md
  - ../plans/2026-07-28-p239-browser-automation.md
  - ../decisions/2026-07-28-browser-automation-instrument.md
---

# P2-40 — gateway'ens accounts[0]-fallback: vælg eksplicit eller fejl ærligt

## Goal

`get_account_id_from_headers` skal aldrig igen returnere en konto brugeren ikke har valgt.
Uden `X-Account-ID` opløses kontoen **eksplicit** til `name = 'Default Account'` (som har et
partielt unique index, `one_default_per_user`), og findes den ikke, returneres `None` — hvorefter
`_require_account_id` giver den fejl der allerede findes. Færdig når (a) en flerkonto-bruger uden
header får *sin defaultkonto eller en fejl*, aldrig en tilfældig konto, og (b) der findes et
instrument der bliver **rødt** hvis fallbacken kommer tilbage — i dag findes det ikke, hverken i
unit- eller browser-laget.

## Context

[Finding'en](../findings/2026-07-28-gateway-falls-back-to-first-account.md) fra P2-39:
`auth.py:99` returnerer `int(accounts[0]...)`, altså den første række account-service
tilfældigvis svarer med. For en enkeltkonto-bruger er det usynligt; for en flerkonto-bruger er
det et plausibelt tal fra den forkerte konto, præsenteret som den valgte. Det er værre end en
tom skærm, fordi en tom skærm bliver rapporteret.

**Finding'en efterlod to ting uafgjorte. Begge er nu afgjort ved læsning, før planen:**

1. **Kan frontenden komme i den tilstand? Ja, og der er ikke engang en vagt.**
   `AuthContext.jsx:22` anser en bruger for logget ind på **tre** nøgler
   (`access_token`, `user_id`, `username`) — `account_id` er ikke blandt dem. `App.jsx:32-33`
   ruter `/` → `/dashboard` og har **ingen** account-guard på nogen af de otte inderside-ruter.
   `LoginPage.jsx:35` navigerer til `/account-selector`, men intet forhindrer brugeren i at gå
   direkte til `/dashboard` med en gyldig token og ingen valgt konto — og
   `graphqlClient.jsx:28` sender så headeren `if (accountId)`, altså ikke.
   `CategoriesPage.jsx:29` tjekker selv `Boolean(localStorage.getItem('account_id'))`, hvilket er
   et spor af at tilstanden er kendt reachable ét sted og uhåndteret på de syv andre.
2. **Er `accounts[0]` stabil? Nej, og der er ikke engang en `ORDER BY`.**
   `postgresql_account_repository.py:23` er `query(AccountModel).filter(...).all()` uden
   sortering, så rækkefølgen er heap-orden. Pointen der gør det konkret: `AccountSelector.jsx:27-44`
   sender en `UPDATE` (`budget_start_day`), og en opdateret række i Postgres skrives som en ny
   version — **så appens egen indstilling kan flytte hvilken konto der er `accounts[0]`.**

**Hvorfor "fejl ærligt" er billigt her:** `graphql_api.py:236-240` har allerede
`_require_account_id`, som kaster `"Account ID required. Send Authorization and/or X-Account-ID
header."` når context'ens `account_id` er falsy. Der skal altså ikke bygges en fejlsti — den er
den sti fallbacken i dag *forhindrer* i at blive nået.

**Hvorfor 'Default Account' og ikke bare `None`:** `account_creation_consumer.py:108` opretter
`name="Default Account"` for hver ny bruger, migration `002` har
`CREATE UNIQUE INDEX one_default_per_user ON "Account" ("User_idUser") WHERE name = 'Default
Account'`, og browser-fixturen `e2e/fixtures/session.js:93` opløser **allerede** kontoen som
`accounts.find(a => a.name === 'Default Account') ?? accounts[0]`. Regelen findes; gateway'en er
det sted der ikke følger den. Vi fjerner samtidig `?? accounts[0]`-halen fra fixturen, så der
kun er én regel i repoet.

## Non-goals

- **Ingen ændring for den normale browser-sti.** Enhver bruger der har været gennem
  `AccountSelector` har `account_id` i localStorage og sender headeren; den gren
  (ejerskabs-check mod account-service, `auth.py:59-80`) røres ikke.
- **Ingen ny vagt i frontenden.** At `/dashboard` kan nås uden valgt konto er en reel mangel,
  men det er en UX-beslutning (redirect til `/account-selector`? vælg default automatisk?) med
  otte ruter i blast radius. Den foreslås som et separat item, se **Follow-ups**. Denne plan gør
  serveren ærlig; den gør ikke klienten klogere.
- **Ingen `ORDER BY` som *fix*.** Sortering ville gøre `accounts[0]` *deterministisk forkert*
  i stedet for tilfældigt forkert. Den tilføjes ikke som løsning her. (Om account-service
  bør sortere sit listesvar af andre grunde er et selvstændigt spørgsmål.)
- Ingen migration, intet schema, ingen event-kontrakt rørt.

## Steps

1. [x] **Mål udgangspunktet, med to konti.** Opstillingen fra finding'en skal genskabes, da
   P3-25's transaktioner er soft-deletet: opret bruger, opret en **anden** konto via
   `POST /api/v1/accounts/`, læg transaktioner på den *anden* konto, og læs `periodOverview`
   med og uden `X-Account-ID`. Forventet før fixet: header → den anden kontos tal, ingen header
   → defaultkontoens nuller, **uden en fejl**. Skriv begge tal ned; de er diskriminatoren i trin 5.
   Ekstra måling der lukker punkt 2 ovenfor: kald `GET /api/v1/accounts/` to gange med en
   `PUT` (budget_start_day) imellem, og se om rækkefølgen skifter. Bliver den ikke ustabil,
   noteres det som et negativt resultat — ikke som at problemet ikke findes.
2. [x] **`services/gateway-service/app/auth.py`** — fallback-grenen (linje 82-102).
   Diff-form: efter `if resp.status_code == 200`, opløs eksplicit i stedet for `accounts[0]`:
   find den konto hvis `name == "Default Account"`; findes den ikke, `return None` og log
   **WARNING** med `user_id` (ikke `exception` — det er ikke en fejl i vores kode, det er en
   bruger uden defaultkonto). Kommentaren over grenen skal sige *hvorfor* eksplicit valg, med
   reference til `one_default_per_user` og til dette item — den nuværende kommentar om 307'eren
   bevares, den er stadig sand og stadig dyrt købt.
3. [x] **`services/gateway-service/tests/unit/test_auth_account_resolution.py`** — ny fil;
   gateway har i dag **ingen test af `auth.py`**. Mindst: (a) header sendt + ejerskab ok → id,
   (b) header sendt + fremmed konto → `None`, (c) ingen header + to konti hvor `Default Account`
   **ikke** er først i listen → default'ens id, (d) ingen header + ingen defaultkonto → `None`,
   (e) ingen header + tom liste → `None`. Test (c) er den der ville have været rød før fixet, og
   den skal bevises rød: byt implementationen tilbage til `accounts[0]` og se den fejle.
   Mock account-service med `respx`/`httpx.MockTransport` — **ikke** en bar `MagicMock`, jf. P3-41.
4. [x] **Luk instrument-hullet: en tokonto-fixture i browser-laget.**
   `services/frontend/e2e/fixtures/session.js` seeder én konto pr. bruger, og det er derfor
   P2-39's mutation blev grøn. Udvid fixturen så den kan seede en **anden** konto med
   transaktioner på den, og skriv én spec der asserterer at dashboardet viser den **valgte**
   kontos tal. Fjern samtidig `?? accounts[0]` på linje 93. Kontrollen for denne test er den
   samme mutation P2-39 brugte og som dengang var grøn: fjern `X-Account-ID` fra
   `graphqlClient.jsx` → **denne test skal nu være rød**. Bliver den ikke det, måler fixturen
   stadig ikke konto-scoping.
5. [x] **Verification** — se nedenfor. Commit-opdeling: trin 2+3 som én commit (fix + den test
   der beviser den), trin 4 som sin egen (instrumentet er selvstændigt værdifuldt), docs som
   den tredje.

## Verification

- `make -C services/gateway-service test` — de fem nye tests, og **test (c) bevist rød** med
  `accounts[0]` genindført. Læs `rc=$?` eksplicit; ingen `| tail` (stående fælde, ramt 6×).
- `make -C services/gateway-service typecheck` — gateway er **ikke** på gaten (98 Strawberry-fejl,
  eget item), så dette er en manuel aflæsning af at `auth.py` ikke bliver værre, ikke en gate.
- `make test-browser` — 3 + den nye spec. Plus kontrollen i trin 4: `X-Account-ID` fjernet fra
  `graphqlClient.jsx`, image genbygget, **den nye spec rød** (og `npm test` fortsat grøn — det er
  netop pointen fra P2-39: browser-laget ser noget jsdom-laget strukturelt ikke kan se).
- **Live, på fuld compose-stak, med to konti** — samme opstilling som trin 1, som treatment mod
  den baseline: uden `X-Account-ID` skal `periodOverview` nu returnere **defaultkontoens** data
  (samme nuller som før, men nu fordi det er et bevidst valg) og en bruger **uden** defaultkonto
  skal få `"Account ID required..."` frem for en fremmed kontos tal. Sidstnævnte kræver at
  defaultkontoen omdøbes — den kan ikke slettes (P2-41).
- `make test-e2e` — 24 passed, forventet upåvirket (den rammer REST-porte direkte, ikke GraphQL).
- `make ci-status` grøn før noget kaldes færdigt.

## Risks & rollback

- **Den reelle risiko er ikke fixet, det er den tilstand fixet afslører.** En bruger der i dag
  når `/dashboard` uden valgt konto ser *forkerte tal*; efter fixet ser hun *en GraphQL-fejl*.
  Det er en forbedring i korrekthed og en forværring i UX, og forværringen er synlig med det
  samme. Det er bevidst — en fejl bliver rapporteret, et forkert tal bliver troet — men det er
  derfor frontend-vagten (Follow-ups) bør følge tæt efter, ikke om et halvt år.
- **En bruger uden `Default Account`** (omdøbt, eller consumeren fejlede ved registrering) mister
  fallbacken helt. Detekteres på den nye WARNING-linje, som netop derfor logger `user_id`.
  Vurderet acceptabelt: alternativet er at gætte, og at gætte er hele fejlen.
- Rollback er én funktion i én fil, uden migration eller kontraktændring: `git revert` af
  fix-commit'en. Instrument-commit'en (trin 4) kan stå alene og bør ikke revertes — den er
  værdifuld uanset hvilken vej fallbacken går.

## Outcome

**Shippet 2026-07-29**, tre commits: `ad0b8d54` (fix + 5 unit-tests), `6050aeb8` (tokonto-fixture
+ spec), plus docs. Begge færdig-kriterier er opfyldt, og begge er bevist med en **kontrol** —
ikke kun med en grøn kørsel.

### Baseline og treatment, målt live (trin 1 + 5)

Opstillingen der gør fejlen synlig kræver at `accounts[0]` **ikke** er defaultkontoen, og den
kan appen selv skabe: omdøb saga-kontoen (det frigør `one_default_per_user`-pladsen), opret
derefter en ny `Default Account` — så er defaultkontoen den *sidste* række.

| bruger 428, `periodOverview(7,2026).totalExpenses` | før fix | efter fix |
|---|---|---|
| `X-Account-ID: 432` ('Gammel Konto', 2 × 777) | 1554,0 | 1554,0 |
| `X-Account-ID: 433` ('Default Account', tom) | 0,0 | 0,0 |
| **ingen header** | **1554,0** ← forkert konto, ingen fejl | **0,0** ← defaultkontoen |

Bruger 427 (hvor `accounts[0]` *er* defaultkontoen) var 0,0 både før og efter — altså uændret
for den normale sti, som Non-goals krævede.

Og den ærlige fejl, efter at 433 blev omdøbt så brugeren ingen defaultkonto har:

```
{"data": null, "errors": [{"message": "Account ID required. Send Authorization and/or X-Account-ID header."}]}
app.auth - WARNING - No 'Default Account' for user 428 and no X-Account-ID sent; resolving to None (P2-40). Accounts found: 2
```

### Rækkefølge-instabiliteten kunne IKKE fremprovokeres — negativt resultat

`GET /accounts/` tre gange med en `PUT budget_start_day` (1→5→1) imellem gav samme rækkefølge
alle tre gange. Fraværet af `ORDER BY` er stadig faktuelt, og heap-orden er stadig ikke en
garanteret rækkefølge — men den påstand fra planen om at appens egen indstilling *kan* flytte
`accounts[0]`, er ikke demonstreret. Instrumentets grænse hører med: tabellen har to rækker, og
en small-field-update kan Postgres sandsynligvis lave HOT/in-page. Fejlen behøvede altså ikke
ustabil rækkefølge for at være reel — det var nok at rækkefølgen var *uspecificeret*, som
opstillingen ovenfor viser.

### Instrumentet (trin 4) — kontrollen blev rød, og kun den

Samme mutation som P2-39 brugte og som dengang gjorde **alle** suiter grønne: `X-Account-ID`
fjernet fra `graphqlClient.jsx`, frontend-imaget genbygget.

| | P2-39 (én konto pr. bruger) | nu (tokonto-fixture) |
|---|---|---|
| `dashboard-scopes-to-selected-account` | fandtes ikke | **1 failed** — kortet viste `10.449,74 kr.` (standardkontoens total) hvor den valgtes `2.718,28` skulle stå |
| øvrige browser-specs | 3 passed | 3 passed |
| `npm test` | 346 passed | 346 passed |

Det bærende designvalg er at den **valgte** konto er den *anden*, ikke standardkontoen. Var
standardkontoen den valgte, ville en server der ignorerer headeren og falder tilbage til
standardkontoen svare rigtigt ved et tilfælde — og kontrollen ville være grøn igen, præcis som
i P2-39.

### Verifikation

- `make -C services/gateway-service test`: **28 passed** (23 før). Test (c) bevist rød med
  `accounts[0]` genindført — og (d) blev rød samtidig, hvilket er en gratis bekræftelse på at
  begge grene af fixet bæres af tests.
- `make test-browser`: **4 passed**, plus kontrollen ovenfor.
- `make test-e2e`: **24 passed**, upåvirket som forventet.
- `make lint-repo`, `make compose-check`: grønne.
- **`make -C services/gateway-service check` er rød — men den var rød før fixet også.**
  `make security` kører `bandit -r app -x tests` uden `-ll -ii`, så et Low/Medium-fund
  (`B105` på `token = ""`, `auth.py:55`) fælder den lokalt, mens CI's `bandit -ll -ii`
  filtrerer det væk. Verificeret ved at køre bandit på `auth.py` fra før fix-commit'en:
  samme rc=1, samme linje. Lokal/CI-divergens, ikke en regression → nyt item, se Follow-ups.
- Planens `make -C services/gateway-service typecheck` **findes ikke**: gateway har hverken
  mypy-target eller mypy-dependency. Aflæsningen blev derfor en manuel gennemgang — de nye
  linjer arbejder på `resp.json()` (altså `Any`) og indfører ingen ny annotationsflade.

### Afdækket undervejs

1. **En fejlbesked der gætter, sender diagnosen det forkerte sted hen.** Browser-suitens
   registrering fejlede med **502**, men fixturens fejltekst nævnte 429 og rate-limit-zonen
   *ubetinget* — så det første minut gik med nginx.conf i stedet for med årsagen, som var
   **P3-45, et allerede kendt åbent item**: `docker compose up -d --build gateway-service`
   genskabte user-service med en ny IP, og nginx opløser upstream-navne ved config-load og
   cacher dem. `docker compose restart frontend` var fixet. Selve fælden er altså ikke ny —
   det nye er at *fejlbeskeden pegede væk fra den*. Hintet er nu betinget af statuskoden, og
   502-grenen navngiver P3-45, så næste gang koster den ét blik i stedet for et minut.
2. **Første udgave af den nye spec fejlede på et forkert prædikat, ikke på produktet.** Den
   ventede på `totalExpenses == 9111.99` for standardkontoen og fik `10449.74` — vores beløb
   plus `dashboard-loads-real-data`s 1337,75, fordi de to specs deler bruger og standardkonto
   i samme worker. Rettet til en **delta**-måling, som er både robust og stadig eksakt
   (`workers: 1`, `fullyParallel: false`).
3. **`?? accounts[0]` stod også i browser-fixturen** og er fjernet, som planen foreskrev. Det
   var samme fejl som gateway'ens: findes 'Default Account' ikke, er `accounts[0]` ikke et
   dårligere svar — det er et svar om en *anden* konto, og suiten ville måle den forkerte.
4. **`prettier` er ikke et værktøj i dette repo** (ingen config, ikke i `package.json`;
   `npm run lint` dækker kun `src/`, ikke `e2e/`). Et `npx prettier --write` omformaterede
   to filer til dobbelte anførselstegn og 80 kolonner og måtte rulles tilbage med
   `git checkout`.

## Follow-ups — begge oprettet som items

- **P3-48: frontend-vagt på de otte inderside-ruter.** `/dashboard` er nåelig med token og uden
  `account_id`; redirect til `/account-selector` er det oplagte, men det er en UX-beslutning, og
  `CategoriesPage.jsx:29` viser at der allerede findes en ad-hoc variant at konsolidere. Nu mere
  presserende end da planen blev skrevet: efter dette fix ser en bruger uden valgt konto en
  GraphQL-fejl frem for forkerte tal. Det er den rigtige retning, men det er stadig en dårlig
  skærm.
- **P3-49: `make security` og CI's bandit er ikke den samme kommando.** Lokalt fælder et
  Low-fund `make check` for gateway; CI ser det ikke (`-ll -ii`). Enten skal targettet have de
  samme flag, eller `B105`-linjen skal have et `# nosec` med item-reference. Som det er nu, er
  `make check` rød på en service uden at noget er i vejen — og det er den slags der gør at
  ingen kører den.
- **Skal account-service sortere sit listesvar?** Ikke et fix for dette item (se Non-goals).
  Målingen gjorde spørgsmålet mindre, ikke større: rækkefølgen var stabil i praksis. Men
  `get_all` uden `ORDER BY` gør enhver forbrugers "første konto" uspecificeret, og
  `AccountSelector`s liste er også usorteret for brugeren.
