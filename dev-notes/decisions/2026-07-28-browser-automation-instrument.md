---
title: Browser-automatisering som ejet instrument — @playwright/test i services/frontend
date: 2026-07-28
status: accepted
backlog: [P2-39]
supersedes: null
promoted-to-adr: null
---

# Browser-automatisering som ejet instrument — `@playwright/test` i `services/frontend`

## Decision

Repoet ejer et browser-lag: **`@playwright/test` som devDependency i `services/frontend/`**,
kørt i det **eksisterende `e2e-tests`-job** (`ci.yml:279-344`), som er det eneste sted i CI hvor
hele stakken inkl. perimeterens nginx på port 3000 faktisk kører.

Første suite er **to tests**, valgt efter fejlmode og ikke efter dækning: (1) dashboardet viser
rigtige tal gennem den rigtige klient — P1-16-klassen; (2) CSP håndhæves i appen, også efter et
klik på en radix-dialog — den måling P3-25 ikke kunne tage. Hård gate fra dag ét.

**Ikke** promoveret til ADR: dette er valget af et instrument, ikke en service-grænse,
data-ejerskab eller et protokolvalg. Hvis suiten senere bliver stedet hvor perimeterens kontrakt
defineres, er *det* ADR-materiale.

## Context

Behovet stod navngivet tre steder uden ID: [STATUS.md](../STATUS.md) under Next up,
[P3-25's plan](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md) trin 6, og
[session-loggen](../sessions/2026-07-28-p325-p227-perimeter-hardening.md).

Argumentet er ikke længere teoretisk, og det er ikke "flere tests". Repoet har i dag to suiter,
og **begge var grønne gennem hele P1-16-regressionen**, hvor hver bruger så
`Fejl: Failed to construct 'URL': Invalid URL` i stedet for data:

- **35 jsdom-filer / 346 tests** (`vite.config.js:60-68`). `graphqlClient.test.jsx:12` mocker
  `GraphQLClient` væk — legitimt for at teste 401-interceptoren, og præcis derfor blind. Målt:
  med regressionen genindført fejler kun de to tests der *ikke* mocker.
- **`tests/e2e/`, 24 tests** — driver host-porte med `httpx` (`conftest.py:8-22`) og går
  **bevidst** uden om perimeteren (`nginx.conf:51`).

Det er altså et **andet instrument**, ikke mere af det samme.
[Findingen](../findings/2026-07-28-graphql-client-rejects-relative-url.md) er lukket af P1-16,
men lektien er ikke: **en `curl`-verifikation beviser transporten, ikke klienten.**

**P3-25 beviste både værdien og grænsen.** Fundet kom fra at *drive* appen — men proben var
headless Chrome med `--dump-dom`, kørt i baggrunden, `sleep`, `kill -9`, plus en throwaway-nginx
på compose-netværket og webroot kopieret til scratchpad. **Intet af det er checket ind; der
findes ingen fil.** Og den ramte sin grænse i samme session: at bevise `'unsafe-inline'`
nødvendig *i appen* kræver at en radix-dialog åbnes — "proben klikker ikke".

## Alternatives considered

- **A — Check den ad hoc-probe ind som script.** Nul nye dependencies, formaliserer noget der
  demonstrerbart virkede. **Afvist:** `--dump-dom` kan ikke klikke, og klikket *er* den
  manglende måling. Vi ville checke præcis den grænse ind som vi træffer beslutningen for at
  komme forbi.
- **B — `pytest-playwright` i `tests/e2e/`.** Genbruger JWT-signeringen (`_env.py:19-39`) og
  health-poll-conftesten, og holder "driv systemet" i én suite i CI-jobbet der allerede findes.
  **Afvist på DX, ikke pris:** assertions om DOM, CSP-violations og netværk skrives i Python om
  en JS-app, og vi mister trace viewer og codegen — som er det der afgør om en browser-suite
  bliver vedligeholdt eller slukket. Suiten deler desuden fixture-behov med den *mockede*
  frontend-suite (samme selectors, samme storage-nøgler), ikke med Python-e2e'en.
- **C — selvstændigt `browser-tests`-CI-job.** Renere adskillelse end at have to test-runnere i
  ét job. **Afvist:** det koster en **anden fuld `docker compose up -d --build`**. Det er dyrere
  end akavetheden ved at `e2e-tests` får et `setup-node`-step.
- **Status quo (bliv ved ad hoc).** Afvist: metoden er ikke reproducerbar af nogen anden end den
  der kørte den, og den efterlod i stedet sin forudsætning som *tilstand i dev-stakken* — bruger
  `csp_probe` (id 368), konto 371, 5 transaktioner, bevidst ikke ryddet op. En verifikation der
  kun kan gentages hvis man ikke rydder op, er ikke et instrument.

## Consequences

**Vi accepterer tre omkostninger, eksplicit:**

1. **To test-runnere i ét CI-job** — vitest i `frontend`, playwright i `e2e-tests`. Prisen for
   ikke at boote stakken to gange.
2. **~30-60 s browser-install** i `e2e-tests` (`npx playwright install --with-deps chromium`,
   med `~/.cache/ms-playwright` cachet). Der er ingen custom image at bage binaryen ind i —
   jobbet kører på `ubuntu-latest` uden container.
3. **Reel flake-risiko, som er ny for dette repo.** Modtrækket er at suiten holdes lille nok til
   at en flake er værd at debugge frem for at slukke. Det er derfor scopet er to tests og ikke en
   portering af de 346.

**Husreglen gælder også her:** hver test skal **verificeres rød ved mutation** før den tælles.
En browser-test der aldrig er set fejle er værre end ingen, fordi den ligner dækning. Det var
netop fejlmoden i P1-16.

**En fixture skal eje session-seedingen, ikke hver test.** Et selvsigneret HS256-token er nok
(`jwt.js:38-44` validerer kun `exp`), som `tests/e2e/_env.py` allerede gør. Men der skal **fem**
localStorage-nøgler til (`authStorage.js:1`), og glemmer man `account_id`, sender `apiClient`
ingen `X-Account-ID` og `periodOverview` svarer med **tavse nuller i stedet for en fejl** — altså
en grøn-udseende test på en tom app. Den fælde hører i fixturen.

**Peger på `127.0.0.1:3000`, ikke `localhost:3000`.** P3-43's første måling ramte en Vite
dev-server på `[::1]:3000` og fik plausible svar fra den forkerte komponent. (`Makefile:49,91`
siger fejlagtigt 5173 — reelt 3000; rettes under P2-39.)

**Hvad det oplåser:** C2-kontrollen fra P3-25 (`'unsafe-inline'` nødvendig i appen), den
DevTools-verifikation `STATUS.md` markerer ubekræftet for SSE/perimeteren, og på sigt den
"søskende-test uden mock" som [findingen om 131 bare mocks](../findings/2026-07-27-sync-trigger-double-value.md)
(P3-41) efterspørger — nu også for frontenden, ikke kun for services.

**Hvad det ikke løser:** de 346 jsdom-tests bliver ikke mindre mockede, og suiten dækker ikke
perimeteren for `tests/e2e/`, som fortsat rammer porte direkte med vilje.
