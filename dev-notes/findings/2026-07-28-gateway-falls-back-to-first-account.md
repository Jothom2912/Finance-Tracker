---
title: Gateway'en falder tilbage til accounts[0] uden X-Account-ID — en flerkonto-bruger får en anden kontos data, uden en fejl
date: 2026-07-28
severity: MEDIUM
status: resolved
scheduled-as: P2-40
resolved-by: commits ad0b8d54 (fix + 5 unit-tests), 6050aeb8 (tokonto-fixture i browser-laget) — [plan + Outcome](../plans/2026-07-28-p240-gateway-explicit-account-resolution.md#outcome)
related:
  - ../plans/2026-07-28-p240-gateway-explicit-account-resolution.md
  - ../plans/2026-07-28-p239-browser-automation.md
  - ../sessions/2026-07-28-p325-p227-perimeter-hardening.md
  - ../findings/2026-07-27-gateway-default-account-307.md
---

# Gateway'en falder tilbage til accounts[0] uden X-Account-ID

**Mangler `X-Account-ID` på en GraphQL-læsning, svarer gateway'en ikke med en fejl — den
læser brugerens FØRSTE konto.** For en bruger med én konto er det usynligt og harmløst.
For en bruger med to er det en læsning mod den forkerte konto, præsenteret som om den var
den valgte.

```python
# services/gateway-service/app/auth.py:92-101 — fallback-grenen
resp = httpx.get(f"{ACCOUNT_SERVICE_URL}/api/v1/accounts/", headers=...)
if resp.status_code == 200:
    accounts = resp.json()
    if accounts:
        return int(accounts[0].get("idAccount") or accounts[0].get("id"))
```

`accounts[0]` er ikke "brugerens valgte konto" og ikke engang eksplicit "standardkontoen" —
det er den første række account-service tilfældigvis returnerer.

## Hvordan det blev fundet — og hvorfor det omskriver en tidligere diagnose

P3-25 målte 2026-07-28 at `periodOverview` gav **tavse nuller** uden `X-Account-ID` (med
header: 25.000/1.629,75, uden: 0/0) og noterede det som "headeren mangler → tomt svar".
Det var den forkerte attribution.

P2-39 forsøgte at bruge netop den mekanisme som mutations-kontrol: `X-Account-ID` blev
fjernet fra `graphqlClient.jsx`, imaget genbygget, og **alle suiter blev grønne**. Kontrollen
tvang forklaringen frem:

```
account_db=# select "idAccount", name, saldo from "Account" where "User_idUser" = 368;
 idAccount |      name       |  saldo
-----------+-----------------+---------
       370 | Default Account |    0.00     <-- accounts[0]
       371 | CSP Probe Konto | 5000.00     <-- den P3-25 målte MED headeren
```

P3-25's testbruger havde **to** konti. Nullerne var ikke et tomt svar; det var et **korrekt
svar om en anden konto**. P2-39's fixture-bruger har én konto, derfor var mutationen grøn.

Begge målinger var rigtige. Kun den ene forklaring var.

## Hvorfor det er værre end en tom skærm

En tom skærm bliver rapporteret. Et plausibelt tal fra den forkerte konto bliver troet.
Fejlmoden er den samme som `X-Account-ID`-ejerskabs-checket i
`project_live_verify_gateway_auth`: **svaret lyver ikke om at det er et svar, kun om hvad det
er et svar på.**

Bemærk asymmetrien i `auth.py`: sendes headeren, ejerskabs-checkes den mod account-service og
et fremmed `account_id` giver `None` → GraphQL-fejl. Udelades den, springes hele det check
over, fordi der ikke er noget at checke. Den strenge sti er den man kan komme til at undgå.

## Hvad der IKKE var afgjort — afklaret 2026-07-28 under planlægningen af P2-40

Begge punkter er afgjort **ved læsning af koden**, ikke ved en kørsel. Det er nok til at
vælge fix, men målingerne står stadig som trin 1 i [planen](../plans/2026-07-28-p240-gateway-explicit-account-resolution.md).

- **Om frontenden i praksis kan komme i den tilstand: ja, og der er ikke en vagt.**
  `AuthContext.jsx:22` anser brugeren for logget ind på tre nøgler (`access_token`,
  `user_id`, `username`); `account_id` er ikke blandt dem. `App.jsx:32-33` ruter `/` →
  `/dashboard`, og **ingen** af de otte inderside-ruter har en account-guard.
  `LoginPage.jsx:35` sender brugeren til `/account-selector`, men intet holder hende der.
  `CategoriesPage.jsx:29` tjekker selv `Boolean(localStorage.getItem('account_id'))` — et spor
  af at tilstanden er kendt reachable ét sted og uhåndteret på de syv andre. Vagten er
  bevidst *ikke* en del af P2-40 (otte ruter i blast radius, og det er en UX-beslutning).
- **Om `accounts[0]` er stabil: der findes ingen `ORDER BY`.**
  `postgresql_account_repository.py:23` er `query(AccountModel).filter(...).all()`, så
  rækkefølgen er heap-orden. Det konkrete: `AccountSelector.jsx:27-44` sender en `UPDATE`
  (`budget_start_day`), og en opdateret række i Postgres skrives som en ny version — **appens
  egen indstilling kan altså flytte hvilken konto der er `accounts[0]`.** Om det faktisk sker
  på vores datamængde er ikke målt endnu.
  **Målt 2026-07-29 (P2-40 trin 1): kunne ikke fremprovokeres.** Tre `GET /accounts/` med en
  `PUT budget_start_day` (1→5→1) imellem gav samme rækkefølge hver gang. Instrumentets grænse
  hører med — to rækker i tabellen, og en small-field-update som Postgres sandsynligvis kan
  lave HOT/in-page. Påstanden ovenfor er altså **ikke** demonstreret. Det ændrer ikke fundet:
  fejlen krævede ikke ustabil rækkefølge, kun *uspecificeret* rækkefølge, og den kunne
  fremkaldes deterministisk (se næste afsnit).

## Hvad der bør gøres

Fallbacken skal vælge **eksplicit**: kontoen med `name = 'Default Account'` (der findes et
unique index `one_default_per_user` netop på den), eller ingen konto og en ærlig fejl. Ikke
`accounts[0]`.

## Reproduktion — den opstilling der gør fejlen deterministisk synlig

Den naive opstilling (opret en anden konto, læg data på den) viser den **ikke**: saga-kontoen
oprettes først, så `accounts[0]` *er* defaultkontoen, og fallbacken svarer rigtigt ved et
tilfælde. Målt: 0,0 både med og uden header.

Trickét er at få defaultkontoen til at være en *senere* række, og det kan appen selv:

1. Registrér en bruger; vent på at sagaen skaber `Default Account`.
2. `PUT /api/v1/accounts/<id>` med et andet `name` — det frigør `one_default_per_user`-pladsen.
3. `POST /api/v1/accounts/` med `name = "Default Account"` → nu er defaultkontoen den sidste.
4. Læg transaktioner på den **første** konto, og læs `periodOverview` uden `X-Account-ID`.

Målt 2026-07-29 på bruger 428 (konti 432 'Gammel Konto' + 433 'Default Account'):
`totalExpenses` = **1554,0 uden header** — den forkerte kontos tal, uden en fejl — mod 0,0 med
`X-Account-ID: 433`. Efter fixet: 0,0 uden header. Det er diskriminatoren.

P3-25's fem transaktioner er soft-deletet (P2-39 trin 8). Konti 370 og 371 på bruger 368 står
stadig i dev-stakken, fordi der ikke findes en sletningssti — se
[../findings/2026-07-28-no-delete-path-for-account-or-user.md].

## Lektien om instrumentet

Browser-suiten kunne **ikke** se dette. Den seedede én konto pr. bruger
(`e2e/fixtures/session.js`), og med én konto er `accounts[0]` altid det rigtige svar. En grøn
browser-suite var altså ikke et løfte om konto-scoping.

**Lukket i P2-40** med `twoAccountSession` + `accountScopedPage` og
`e2e/dashboard-scopes-to-selected-account.spec.js`. Det bærende designvalg: den **valgte** konto
er den *anden*, ikke standardkontoen — ellers ville en server der ignorerer `X-Account-ID` og
falder tilbage til standardkontoen svare rigtigt ved et tilfælde, og kontrollen ville være grøn
igen. Med samme mutation som i P2-39 (`X-Account-ID` fjernet fra `graphqlClient.jsx`) er den nye
spec nu **rød** — kortet viste standardkontoens `10.449,74 kr.` hvor den valgtes `2.718,28`
skulle stå — mens de tre øvrige browser-specs og alle 346 jsdom-tests forblev grønne.
