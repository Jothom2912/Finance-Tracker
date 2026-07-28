---
title: graphql-request afviser den relative URL P3-43 gav den — hele GraphQL-læsestien er død i browseren
date: 2026-07-28
severity: HIGH
status: open
scheduled-as: P1-16
related:
  - ../plans/2026-07-28-p343-nginx-perimeter.md
  - ../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md
  - ../../docs/adr/0005-nginx-as-security-perimeter.md
---

# graphql-request afviser den relative URL P3-43 gav den

**`GraphQLClient` kaster `TypeError: Invalid URL` på en relativ sti, så hver GraphQL-læsning
i frontenden fejler i browseren.** Dashboardet render `Fejl: Failed to construct 'URL':
Invalid URL` i stedet for data. Introduceret 2026-07-28 af `c0418646` (P3-43 trin 2), samme
dag som det blev fundet.

## Beviset

Tre lag, bevidst uafhængige, fordi det første alene kunne være et probe-artefakt:

1. **I en rigtig browser-engine.** Headless Chrome mod det byggede bundle, med en gyldig
   session seedet i `localStorage`: `/dashboard` render nav og layout, men indholdet er
   erstattet af `Fejl: Failed to construct 'URL': Invalid URL`.
2. **Uden browseren og uden proben.** `graphql-request` 7.4.0 i node mod samme
   `node_modules`:
   ```
   new GraphQLClient('/api/v1/graphql').request(gql`{ __typename }`)
     → TypeError: Invalid URL
   new GraphQLClient('http://127.0.0.1:8010/api/v1/graphql').request(…)
     → ok
   ```
   Biblioteket kalder `new URL(url)` uden base. En relativ sti er ikke en gyldig absolut URL,
   så konstruktionen kaster før der sendes noget.
3. **Årsagen er daterbar.** `src/api/graphqlClient.jsx:5` bygger
   `GRAPHQL_URL = ${GATEWAY_SERVICE_URL}/graphql`, og `GATEWAY_SERVICE_URL` blev `'/api/v1'`
   i `c0418646` — *"feat(frontend): relative URLs — browseren taler med én origin
   (P3-43 trin 2)"*.

## Blast radius

`gqlRequest`/`getGraphQLClient` bruges af `useDashboardData`, `usePeriodOverview`,
`useTransactionSearch` og (via dem) `useTransactions` — altså af `DashboardOverview`,
`TransactionsPage` og `CategoriesPage`. Det er kerne-læsestierne.

**`fetch`-baserede kald er upåvirkede.** `fetch` opløser relative URLs mod dokumentets base;
det er kun biblioteker der selv konstruerer en `URL` der brækker. Målt: der er ingen andre
`new URL(` i `src/`, og `@microsoft/fetch-event-source` sender videre til `fetch`, så
chat-SSE'ens URL-håndtering er ikke i samme klasse. Perimeteren og de relative URLs er
altså ikke forkerte som form — præcis ét bibliotek kan ikke tage imod dem.

## Hvorfor ingen gate fangede det

Det er den vigtigste del, fordi begge tavsheder allerede var kendte mønstre i repoet:

- **P3-43 verificerede GraphQL med `curl` same-origin**, og STATUS.md's *"GraphQL leverer
  rigtig aggregeret data same-origin"* er sandt — **om transporten**. nginx proxyer korrekt.
  Fejlen ligger i klienten, som `curl` per definition ikke kører. En transport-måling kan
  ikke bevise en klient.
- **De 344 frontend-tests er blinde ved konstruktion.** `src/api/graphqlClient.test.jsx:12`
  gør `vi.mock('graphql-request', …)` og erstatter `GraphQLClient` med en mock, så den rigtige
  konstruktør — den der kaster — aldrig kører. Mocket *er* blindheden. Det er samme klasse som
  [de 131 bare mocks uden `spec`](2026-07-27-sync-trigger-double-value.md) (P3-41) og samme
  klasse som at frontend-testene bestod med P3-43's URL-fejl genindført fordi de mocker
  `fetch` — men denne gang slap en ægte regression hele vejen til master.

**Fundet kom fra en kontrol i et urelateret item.** P3-25's CSP-verifikation krævede en
autentificeret side i en rigtig browser-engine, fordi jsdom ikke håndhæver CSP. Ingen leden
efter denne bug fandt den; kravet om at *drive appen* gjorde. Det er argumentet for at et
browser-drevet smoke-flow er en gate og ikke en luksus.

## Fix-retning

Giv klienten en absolut URL bygget i runtime fra `window.location.origin`, så
`serviceUrls.js` kan blive relativ (perimeter-egenskaben fra ADR-0005 bevares) mens
biblioteket får den absolutte URL det kræver. Ændringen hører i `graphqlClient.jsx`, ikke i
`serviceUrls.js` — det er klientens krav, ikke konfigurationens.

**Testen må ikke mocke `graphql-request`.** En test der asserterer på den URL klienten reelt
konstrueres med er den eneste form der ville have fanget dette; en mocket konstruktør
reproducerer blindheden.
