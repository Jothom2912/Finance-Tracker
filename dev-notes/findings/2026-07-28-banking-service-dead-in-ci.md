---
title: banking-service har aldrig kørt i CI — PEM-mountet bliver en mappe, og dashboardet svarede 500 uden at nogen gate så det
date: 2026-07-28
severity: MEDIUM
status: resolved
resolved-by: P2-39 (2026-07-28) — throwaway `openssl genrsa`-PEM i CI, port 8009 i `Wait for system`, og 5xx fanges nu med URL i browser-fixturen. Den ÅBNE del (500 vs. 503 fra banking, og at 44 af 53 compose-services stadig ingen gate har) er ikke lukket her.
scheduled-as: P2-39
related:
  - ../plans/2026-07-28-p239-browser-automation.md
  - ../sessions/2026-07-28-p239-browser-automation.md
  - ../findings/2026-07-28-ci-job-can-hang-undetected.md
---

# banking-service har aldrig kørt i CI

**`docker compose up` i CI starter en banking-service der dør ved boot, og dashboardet
svarer derfor 500 på `/api/v1/bank/connections` ved hver sideindlæsning.** Det har været
tilfældet så længe `e2e-tests` har kørt hele stakken, og ingen gate kunne se det.

```
banking-service-1 | app.adapters.outbound.enable_banking_client.BankConfigError:
banking-service-1 |   Cannot read PEM at /app/enablebanking.pem: IsADirectoryError(21, 'Is a directory')
```

## Mekanismen — og hvorfor fejlen ikke siger "file not found"

```yaml
# docker-compose.yml:40
- ${ENABLE_BANKING_ACTIVE_PEM_PATH:-./enablebanking-sandbox.pem}:/app/enablebanking.pem:ro
```

Findes kildefilen ikke, **opretter Docker en mappe** på mount-punktet frem for at fejle.
`Path(...).read_bytes()` møder derfor en mappe, ikke et fravær — og
`enable_banking_client.py:71-81` læser PEM'en *og* signerer et RS256-JWT som smoke-test i
`__init__`, så servicen kan ikke starte.

Lokalt findes filen (`.env` peger på en rigtig sandbox-PEM), så det er en ren
CI-vs-lokal-divergens. Det rammer også en frisk klon uden `.env`.

## Hvorfor tre gates var blinde

1. **`tests/e2e/` rører ikke banking.** 24 tests, ingen af dem på port 8009.
2. **`Wait for system` pollede ikke 8009.** Loopet dækkede 8001-8006, 8010, 8012 — så en død
   banking-service passerede opstarts-checket lydløst.
3. **De 346 jsdom-tests mocker `api/bank.jsx`.** En 500 fra en service der ikke kører, er
   ikke en tilstand en mock kan komme i.

Bemærk mønstret: det var ikke en manglende test. Det var at **ingen af de tre instrumenter
kiggede på den ene ting der var i stykker**, og at systemet svarede 200 på alt de spurgte om.

## Hvordan det blev fundet

P2-39's browser-suite, **første kørsel i CI**. Test 1 fejlede på sin sidste assertion —
`pageErrors` var ikke tom:

```
Error: appen skrev fejl til konsollen:
console.error: Failed to load resource: the server responded with a status of 500
console.error: Failed to load resource: the server responded with a status of 500
```

Beløbs-assertionerne var alle grønne. Dashboardet *virkede*; det larmede bare 500 imens.
To fejl og ikke én, fordi `toPass`-loopet genindlæste siden to gange mens ES haltede — én
per load.

**Attribueringen krævede en lokal reproduktion**, fordi browserens egen konsolbesked ikke
indeholder URL'en. `docker compose stop banking-service` + suiten gav samme fejlklasse
(502 i stedet for 500: nginx kan ikke nå en stoppet container, mens CI's container fandtes
og svarede 500). Det pegede på banking, og compose-logsene i CI-outputtet bekræftede det.

## Rettelser

1. **`openssl genrsa -out enablebanking-sandbox.pem 2048` før `compose up` i CI.** En
   throwaway-nøgle er nok: CI kalder ikke Enable Banking, nøglen skal kunne *læses* og kunne
   *signere*. Verificeret: en `genrsa`-nøgle signerer RS256 med `pyjwt`.
2. **Port 8009 tilføjet til `Wait for system`.** En død banking-service fejler nu i det step
   der findes for at fange det, med servicens egne logs — ikke som en 500 i en browser-konsol
   tre steps senere.
3. **Fixturen fanger 5xx på response-grænsen med URL på** (`e2e/fixtures/session.js`).
   Browserens URL-løse `Failed to load resource` filtreres væk, så hver 5xx rapporteres én
   gang, med adresse. Fejlbeskeden fra CI var alt man havde, og den nævnte ikke servicen.

## Hvad der ikke er afgjort

- **Om et 500 fra en valgfri integration er en produktfejl.** `BankConnectionWidget` fanger
  fejlen og render en tilstand, men servicen svarer 500 hvor konventionen for utilgængelig
  bank-forbindelse er **503** (`BankConnectionInactive` → 503 + WARNING). En 500 for
  "integrationen er ikke konfigureret" er ikke en ærlig statuskode. Ikke rørt her — P2-39's
  non-goal er nul produktkode.
- **Hvad ellers der er dødt i CI uden at nogen ved det.** Kontrollen der findes nu, er
  ventetiden på ni porte. Compose kører **53 services**; de resterende har ingen gate.
