---
title: Gateway'en falder tilbage til accounts[0] uden X-Account-ID — en flerkonto-bruger får en anden kontos data, uden en fejl
date: 2026-07-28
severity: MEDIUM
status: open
scheduled-as: P2-40
related:
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

## Hvad der IKKE er afgjort

- **Om frontenden i praksis kan komme i den tilstand.** `authStorage.js` erklærer
  `account_id`, og `AccountSelector.jsx:20-25` sætter den — men `AuthContext.jsx:17-35`
  kræver kun tre af de fem nøgler for at anse brugeren for logget ind. En session hvor
  `account_id` mangler, men token findes, er altså mulig efter appens egne regler. Om der
  findes en rute dertil, er ikke målt.
- **Om `accounts[0]` er stabil.** Account-service sorterer ikke eksplicit; rækkefølgen er
  DB'ens. To kald kan i princippet svare forskelligt.

## Hvad der bør gøres

Fallbacken skal vælge **eksplicit**: kontoen med `name = 'Default Account'` (der findes et
unique index `one_default_per_user` netop på den), eller ingen konto og en ærlig fejl. Ikke
`accounts[0]`.

## Reproduktion

P3-25's fem transaktioner er soft-deletet (P2-39 trin 8), så opstillingen skal genskabes:
opret en bruger, opret en **anden** konto via `POST /api/v1/accounts/`, læg transaktioner på
den anden konto, og læs `periodOverview` med og uden `X-Account-ID`. Konti 370 og 371 på
bruger 368 står stadig i dev-stakken, fordi der ikke findes en sletningssti — se
[../findings/2026-07-28-no-delete-path-for-account-or-user.md].

## Lektien om instrumentet

Browser-suiten kan **ikke** se dette. Den seeder én konto pr. bruger
(`e2e/fixtures/session.js`), og med én konto er `accounts[0]` altid det rigtige svar. En
grøn browser-suite er ikke et løfte om konto-scoping — det kræver en fixture med to konti,
og den er ikke skrevet.
