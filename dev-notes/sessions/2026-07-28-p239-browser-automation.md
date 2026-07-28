---
title: P2-39 — browser-automatisering som ejet instrument
date: 2026-07-28
backlog-items: [P2-39]
related:
  - ../plans/2026-07-28-p239-browser-automation.md
  - ../decisions/2026-07-28-browser-automation-instrument.md
  - ../findings/2026-07-28-gateway-falls-back-to-first-account.md
  - ../findings/2026-07-28-no-delete-path-for-account-or-user.md
---

# P2-39 — browser-automatisering som ejet instrument

**Shippet.** 3 Playwright-tests i `services/frontend/e2e/`, hård gate i `e2e-tests`, ~16 s
lokalt via `make test-browser`. Ingen produktkode ændret.

## Kronologi

Trin 1-2 (Playwright + config, session-fixturen) var kørt i en tidligere session. Denne
session tog 3-9.

| Trin | Commit | Note |
|---|---|---|
| 3 — test 1 | `d632f1e9` | Asserterer på **beløb** (4.242,42 / 1.337,75 / netto 2.904,67), ikke på at siden mounter |
| 4 — test 2 + C2 | `90a11e3c` | CSP-testen der kan klikke; C2 afgjort med et tal |
| 5 — mutations-kontrol | `cb9d6974` | To kandidater faldt, den tredje holdt |
| 6 — CI | `ce339e5f` | + `timeout-minutes: 30`, + port 3000 i wait-loopet |
| 7 — Makefile | `9ea54d38` | `make test-browser`; 5173 → 3000 |
| 8-9 — oprydning + docs | (denne) | Kun transaktionerne kunne ryddes |

## Det der kostede tid, og hvad det var værd

### Mutations-kontrollen faldt to gange — og begge fald var fund

Planen sagde: genindfør P1-16, forvent browser rød + `npm test` grøn. Målingen:
**`npm test` blev også rød** (2 af 346). P1-16 fik en jsdom-regressionstest
(`graphqlClient.url.test.jsx`) da den blev rettet, så linjen er dobbeltdækket. Kriteriet var
skrevet uden det — og det er ikke en sløsethed, men en systematisk fejl: **man vælger
instinktivt den bug der motiverede itemet, og det er netop den der er blevet dækket.**

Kandidat 2: fjern `X-Account-ID` fra `graphqlClient`. Rebuild, kør. **Grøn i begge suiter.**
Det tvang forklaringen frem, og den var vigtigere end kontrollen:

```
account_db=# select "idAccount", name, saldo from "Account" where "User_idUser" = 368;
       370 | Default Account |    0.00   <-- accounts[0]
       371 | CSP Probe Konto | 5000.00   <-- den P3-25 målte MED headeren
```

Gateway'en falder tilbage til `accounts[0]` (`auth.py:99`). P3-25's "tavse nuller uden
headeren" var altså **et korrekt svar om den forkerte konto** — ikke et tomt svar. Vores egen
fixture har én konto, derfor var mutationen grøn. → **P2-40**.

Kandidat 3 holdt: `totalIncome → totalIncomeTYPO` i `DASHBOARD_QUERY`. **`npm test` 346
passed, browser 2 failed.** GraphQL-dokumentet valideres mod det rigtige schema af intet andet
i repoet, fordi `useDashboardData.test.jsx:6` mocker klienten væk.

### Grøn-på-ingenting ramte inde i instrumentet selv

`script-src 'none'`-kontrollen gjorde begge målende tests røde — og lod **fixturens egen
vagt** være grøn. Den asserterede på localStorage-nøgler og URL, som alle består på en tom
HTML-side uden en linje kørende JavaScript. Hærdet med en assertion om at appen mountede.
Fejlmoden itemet findes for at bekæmpe, i første forsøg, inde i itemet.

### To compose-fælder der ser ud som testfejl

1. **`docker compose restart` gendanner ikke en muteret fil i containeren.** Mutationen ligger
   i det writable layer. Kostede en kørsel hvor `style-src` stadig var muteret under
   `script-src`-kontrollen. `up -d --force-recreate` er svaret.
2. **`compose up -d --build frontend` trækker alle ti `depends_on` med.** Kørslen ramte
   10-minutters-timeouten, blev afbrudt midt i recreate, og efterlod `ai-service` +
   `gateway-service` i `Created` — hvorefter nginx nægtede at starte med *"host not found in
   upstream"*, præcis som `nginx.conf`s egen kommentar forudsiger. `--no-deps` ved gen-build af
   frontenden alene.

### Trin 8 forudsatte en kapabilitet der ikke fandtes

"Slet bruger 368, konti 370/371, fem transaktioner." Hverken account- eller user-service
eksponerer **DELETE**, og `Account` har ingen `is_deleted`-kolonne. Antagelsen havde overlevet
planlægning og godkendelse. → **P2-41**.

De fem transaktioner blev ryddet via API'et, ikke i DB'en — og hele kæden blev verificeret,
fordi soft-delete gør det utydeligt om noget skete: 5 × **204** → `is_deleted: true` på alle
fem i `transactions_v2` (doc-count falder *ikke*) → `periodOverview` fra 25.000/1.629,75 til
**0/0**. Bagefter: browser 3 passed, `make test-e2e` 24 passed.

## Målinger

| Hvad | Udfald |
|---|---|
| C2: `style-src` uden `'unsafe-inline'` | **1 violation**, `style-src-elem`/inline, ved dialog-klik · **0** på `/dashboard` |
| Kontrol: `script-src 'none'` | appen mounter ikke; 2 tests røde |
| Instrumentet er nyt | `npm test` **346**, browser **2 failed** på samme kode |
| Efter oprydning | browser **3 passed**, e2e **24 passed**, `notes-check` 134 notes clean |

## Efterspil: første CI-kørsel var rød, og fundet var ægte

Suiten fandt noget på sin **første kørsel i CI** som ingen gate havde set før: i CI kan
banking-service ikke læse sin PEM, så `/bank/connections` svarer 500 — og dashboardet kalder
den ved hver load. Den manglende fil får Docker til at oprette en *mappe* på mount-punktet
(deraf `IsADirectoryError`, ikke "file not found"). Beløbs-assertionerne var grønne — appen *virkede*, den larmede bare
en serverfejl imens. Kun `pageErrors`-assertionen fangede det.
[Finding](../findings/2026-07-28-banking-service-dead-in-ci.md), åben del → **P2-42**.

To lektioner ud over selve bug'en:

- **Fejlbeskeden var utilstrækkelig, og det kostede en reproduktion.** Browserens egen
  konsolbesked (`Failed to load resource: … 500`) indeholder **ikke** URL'en, så CI-outputtet
  sagde ikke hvilken service det var. Fixturen fanger nu 5xx på response-grænsen *med* adresse,
  og filtrerer browserens URL-løse variant væk. Et instrument der kan se en fejl, men ikke sige
  hvor den er, er halvt færdigt.
- **Min egen rettelse var forkert diagnosticeret, og det var kontrollen der afslørede det.**
  Jeg skrev at servicen døde ved boot og tilføjede port 8009 til `Wait for system` som gaten.
  Næste kørsel: **`port 8009: healthy`** — og stadig 500 på `/bank/connections`.
  `EnableBankingClient` konstrueres per request, så `/health` rører aldrig PEM'en. **Et
  liveness-probe kan ikke se en brudt afhængighed.** Porten er beholdt, men den er ikke
  kontrollen for dette.
- **Og fixet skulle have to forsøg.** `openssl genrsa` rettede filens eksistens og flyttede
  fejlen fra `IsADirectoryError` til `PermissionError`: den skriver mode **600** ejet af
  runneren, mens containeren kører som `uid=10001 (appuser)`. Den lokale PEM er 644 — hele
  divergensen sad i en filrettighed, ikke i konfigurationen.

## Åbne ender

- **P2-40** (gateway `accounts[0]`) og **P2-41** (ingen sletningssti) er skrevet, ikke løst.
- **Suiten kan ikke se konto-scoping.** Én konto pr. bruger; det kræver en flerkonto-fixture.
- **Gaten er grøn i CI** (run `30400981674`): 3 browser-tests navngivet i outputtet, 18,9 s,
  oven i de 24 Python-e2e. CI's mekanik virkede i første forsøg (chromium-install ~28 s uden
  cache-hit, port-3000-ventetiden, artifact-upload); det var *appen* der var rød, og de to røde
  kørsler er dermed instrumentets første to fund frem for opstartsproblemer.
- Bruger `csp_probe` (368) og konti 370/371 står stadig i dev-stakken.
