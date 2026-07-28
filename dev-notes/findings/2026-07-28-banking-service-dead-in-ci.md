---
title: banking-service har aldrig kunnet svare på /bank/connections i CI — PEM'en er ulæselig, og et /health-probe kan ikke se det
date: 2026-07-28
severity: MEDIUM
status: resolved
resolved-by: P2-39 (2026-07-28) — throwaway `openssl genrsa`-PEM **med `chmod 644`** i CI, plus 5xx med URL i browser-fixturen. Det tog TO forsøg: første fix rettede kun filens eksistens og flyttede fejlen fra `IsADirectoryError` til `PermissionError`. Den ÅBNE del (500 vs. 503 fra banking) er ikke lukket her.
scheduled-as: P2-39
related:
  - ../plans/2026-07-28-p239-browser-automation.md
  - ../sessions/2026-07-28-p239-browser-automation.md
  - ../findings/2026-07-28-ci-job-can-hang-undetected.md
---

# banking-service har aldrig kunnet svare på `/bank/connections` i CI

**I CI kan banking-service ikke læse sin PEM, så `GET /api/v1/bank/connections` svarer 500 —
og dashboardet kalder den ved hver sideindlæsning.** Det har været tilfældet så længe
`e2e-tests` har kørt hele stakken, og ingen gate kunne se det.

**Rettelse til denne notes første udgave:** den påstod at servicen *døde ved boot*. Det er
forkert, og målingen der modsagde den var min egen kontrol — port 8009 blev tilføjet til
`Wait for system`, og den **bestod**:

```
port 8009: healthy
...
banking-service-1 | INFO: Application startup complete.
banking-service-1 | INFO: 127.0.0.1:34014 - "GET /health HTTP/1.1" 200 OK
banking-service-1 | INFO: 172.18.0.46:40984 - "GET /api/v1/bank/connections?account_id=16 HTTP/1.0" 500
banking-service-1 |   File "/app/app/adapters/outbound/enable_banking_client.py", line 71, in __init__
banking-service-1 |     self._private_key = Path(config.key_path).read_bytes()
banking-service-1 | PermissionError: [Errno 13] Permission denied: '/app/enablebanking.pem'
```

Servicen starter fint: migrations kører, uvicorn er oppe, `/health` svarer 200 hele vejen.
`EnableBankingClient` konstrueres **per request**, så PEM-læsningen sker på request-stien —
ikke ved opstart.

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
2. **`Wait for system` pollede ikke 8009** — men det ville ikke have hjulpet. Porten er
   tilføjet nu, og den er **grøn på præcis den tilstand denne note handler om**, fordi
   `/health` ikke rører PEM'en. Et liveness-probe kan ikke se en brudt afhængighed; det ser
   at processen lever. Det er den vigtigste enkeltlektion her.
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

1. **`openssl genrsa` + `chmod 644` før `compose up` i CI.** To forsøg, og det første var
   lærerigt: `genrsa` alene rettede filens *eksistens* og flyttede fejlen fra
   `IsADirectoryError` til `PermissionError`, fordi den skriver mode **600** ejet af runneren
   mens containeren kører som `uid=10001 (appuser)`. Lokalt er filen 644 — deraf hele
   CI-vs-lokal-divergensen. En throwaway-nøgle er nok: CI kalder ikke Enable Banking, nøglen
   skal kunne *læses* og kunne *signere*. Verificeret: en `genrsa`-nøgle signerer RS256 med
   `pyjwt`.
2. **Port 8009 tilføjet til `Wait for system`** — beholdt, men uden at foregive at være
   kontrollen for dette: den var grøn mens bug'en var i kraft. Den fanger en reelt død
   service, ikke en brudt afhængighed.
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
