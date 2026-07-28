---
title: nginx er sikkerhedsperimeteren, ikke gateway-service
date: 2026-07-28
status: accepted
backlog: [P3-24]
supersedes: null
promoted-to-adr: docs/adr/0005-nginx-as-security-perimeter.md
---

# nginx er sikkerhedsperimeteren, ikke gateway-service

## Decision

Frontendens egen nginx bliver perimeteren: browseren taler med **én** origin, og nginx
`proxy_pass`'er per path til services over compose-netværkets interne DNS. Gateway-service
forbliver CQRS-læsesiden og får ikke dobbeltrolle som skrive-proxy.

Fuld begrundelse, verificeret ruter-tabel og de fire implementeringsfælder:
**[ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md)**.

## Context

P3-24's ADR-halvdel; den blokerede [P3-25](../backlog/BACKLOG.md#p3-25) og
[P2-27](../backlog/BACKLOG.md#p2-27), som begge skal vide *hvor* de lander.
Fra [sweepets SEC-3](../findings/2026-07-26-product-surface-sweep.md).

Det fund der omformede beslutningen: **der findes ikke en deployment i dag hvor en perimeter
ville være nåelig.** k8s har 30 ClusterIP-Services og hverken Ingress, NodePort eller
LoadBalancer — adgang sker via `kubectl port-forward`. Og frontendens `VITE_*`-vars er ikke
sat nogen steder, så de hardcodede `localhost:800X`-fallbacks er dem der bygges ind i imaget.
ADR'en forpligter derfor en *form* frem for at udbedre en produktion.

## Alternatives considered

- **gateway-service som perimeter** — afvist: en Python-hop foran hver write, CQRS-læsesiden
  bliver også skrive-chokepunkt, og ruter-tabellen skal vedligeholdes i FastAPI-kode frem for
  i den komponent der allerede står i trafikkens vej. Den eneste reelle fordel (auth ét sted)
  er unødvendig — hver service validerer allerede JWT selv.
- **Accepter multi-origin** — afvist: ikke gratis. Koster allerede 11 `CORSMiddleware`
  der skal holdes i sync, blokerer HttpOnly-cookie definitivt, tvinger P2-27 til N
  implementeringer og efterlader P3-25's CSP delvis. Prisen er løbende, besparelsen engangs.

## Consequences

Oplåser P3-25 (headers + HttpOnly-cookie ét sted), P2-27 (`limit_req`-zone frem for `slowapi`
× N) og sanering af de 11 CORS-konfigurationer.

Fælderne står i ADR'ens sidste afsnit og er alle verificeret, ikke formodet: SSE på
`/api/v1/chat/stream` brækker på nginx' default-buffering; perimeteren skal være en positiv
allowlist, ellers publicerer den de `INTERNAL_API_KEY`-vogtede ruter; service-portene
8001–8012 forbliver åbne indtil e2e's otte health-polls har en vej ind; og intet bevogter
nginx.conf mod drift når en ny service tilføjes.

Løser **ikke** credentials — `guest:guest`, `xpack.security.enabled: "false"` og
Postgres-passwords i klartekst er urørte, og alt der kører *på* maskinen når stadig datastores
uden auth (se [datastore-halvdelens Outcome](../plans/2026-07-28-p324-datastore-loopback-bind.md#outcome)).
Perimeteren handler om browser-trafik, ikke om at hærde datastores.
