# ADR-0005: nginx er sikkerhedsperimeteren — ikke gateway-service

Dato: 2026-07-28
Status: Accepteret (beslutning; ingen implementering endnu — se Konsekvenser)
Backlog: P3-24 · Fund: [SEC-3](../../dev-notes/findings/2026-07-26-product-surface-sweep.md)

## Kontekst

Sweepets SEC-3 kaldte det "the gateway is not a perimeter" og gjorde det til rod for tre
ellers urelaterede symptomer: ingen plads til rate limiting eller CSP, JWT'en kan ikke flytte
til en HttpOnly-cookie, og Swagger står åben på alle 12 services. Beslutningen blev udskudt
til denne ADR, fordi P3-25 og P2-27 begge skal vide *hvor* de lander.

Målt 2026-07-28, ikke antaget:

- **gateway-service er ikke en proxy.** `main.py` monterer tre ting: `/health`, en saga-router
  og GraphQL på `/api/v1/graphql`. Den er CQRS-læsesiden. Writes går uden om den, direkte fra
  browseren til hver service.
- **Browseren taler med ti origins**, listet i `services/frontend/src/config/serviceUrls.js`.
- **De ti er ikke konfigurerbare i praksis.** Filen læser `VITE_*`-vars med
  `http://localhost:800X` som fallback, men de vars er **ikke sat nogen steder** — ikke i
  compose, ikke i k8s. Der er heller ingen vite dev-proxy. De hardcodede localhost-URL'er er
  altså dem der bygges ind i imaget.
- **k8s har ingen indgang overhovedet.** 30 `Service`-manifester, alle ClusterIP; ingen
  Ingress, ingen NodePort, ingen LoadBalancer. Adgang sker via `scripts/k8s-port-forward.sh`,
  som gendanner præcis de samme `localhost:800X`-origins.
- **`services/frontend/nginx.conf` er 12 linjer** — SPA-fallback, ingen proxy, ingen headers.
- **11 services bærer hver sin `CORSMiddleware`** plus en `CORS_ORIGINS`-env i compose.

Det sidste punkt omformer beslutningen: **der findes ikke en deployment i dag hvor en perimeter
ville være nåelig.** Frontenden i k8s ville få browseren til at kalde `localhost:8001`; det
virker kun under port-forward. Denne ADR er derfor ikke en udbedring af produktion — den
forpligter en *form*, mens der endnu ikke er noget at bryde.

Datastore-halvdelen af P3-24 lukkede separat samme dag (`5ea37f0d`): de 14 datastore-porte
binder nu loopback. Service-portene 8001–8012 gør ikke, og det er stadig sandt efter denne ADR.

## Beslutning

**Frontendens egen nginx er perimeteren.** Browseren taler med præcis én origin; nginx
`proxy_pass`'er per path til services på compose-netværkets interne DNS.

```
browser ──► nginx :80 ──┬─► user-service:8001
   (én origin)          ├─► transaction-service:8002
                        ├─► gateway-service:8010   (GraphQL reads)
                        └─► ... 7 mere
```

Gateway-service forbliver hvad den er — CQRS-læsesiden — og får ikke en dobbeltrolle.

**Ruter-tabellen er verificeret entydig.** Alle ti services adskiller sig på andet
path-segment efter `/api/v1`, så der er ingen kollision at løse:

| Path | Service | Port |
|---|---|---|
| `/api/v1/users` | user | 8001 |
| `/api/v1/transactions`, `/api/v1/planned-transactions` | transaction | 8002 |
| `/api/v1/budgets`, `/api/v1/monthly-budgets` | budget | 8003 |
| `/api/v1/accounts`, `/api/v1/account-groups` | account | 8004 |
| `/api/v1/categories`, `/api/v1/subcategories`, `/api/v1/rules` | categorization | 8005 |
| `/api/v1/goals` | goal | 8006 |
| `/api/v1/chat` | ai | 8007 |
| `/api/v1/notifications` | notification | 8008 |
| `/api/v1/bank` | banking | 8009 |
| `/api/v1/graphql`, `/api/v1/sagas` | gateway | 8010 |

## Alternativer

**gateway-service som perimeter — afvist.** Den ville skulle reverse-proxye REST-writes
oveni sin GraphQL-rolle. Det lægger en Python-hop foran hver eneste write, gør CQRS-læsesiden
til også at være skrive-chokepunkt, og kræver at ruter-tabellen ovenfor vedligeholdes i
FastAPI-kode frem for i den komponent der allerede står i trafikkens vej. nginx gør præcis
dette hurtigere og med færre bevægelige dele. Den eneste reelle fordel — auth ét sted i Python
— er ikke nødvendig, fordi hver service allerede validerer JWT selv.

**Accepter multi-origin som skrevet trade-off — afvist.** Det er ikke gratis, hvilket var
fristelsen. Det koster allerede 11 `CORSMiddleware`-konfigurationer der skal holdes i sync,
det blokerer HttpOnly-cookie definitivt (ti origins), det tvinger P2-27 til at blive N
implementeringer i stedet for én `limit_req`-zone, og det efterlader P3-25's CSP delvis. Prisen
betales løbende; besparelsen er engangs.

## Konsekvenser

**Oplåser:**

- **P3-25** — CSP, HSTS, `X-Frame-Options`, `Referrer-Policy` ét sted. HttpOnly-cookie bliver
  mulig, fordi der kun er én origin.
- **P2-27** — rate limiting som en `limit_req`-zone i nginx frem for `slowapi` i N services.
- **Sanering:** de 11 `CORSMiddleware` + `CORS_ORIGINS` bliver overflødige, fordi kald bliver
  same-origin.

**Kræver:**

- Frontendens `serviceUrls.js` skal bruge relative paths i stedet for absolutte.
- I k8s: port-forward kun frontend. På sigt en Ingress — som i dag slet ikke findes.

**Fire ting der ikke må opdages under implementering:**

1. **SSE brækker på default-config.** `ai-service` returnerer `EventSourceResponse`
   (`app/adapters/inbound/stream_api.py`) på `/api/v1/chat/stream`. nginx buffrer som default,
   hvilket ødelægger streaming. Kræver `proxy_buffering off` og hævet `proxy_read_timeout` på
   netop den location.
2. **Perimeteren skal være en positiv allowlist, ikke en catch-all.** `/api/v1/internal/*`
   (account-service) og `/api/v1/categorize` (categorization) er `INTERNAL_API_KEY`-vogtede
   service-til-service-ruter. En `location /api/ { proxy_pass … }` ville publicere dem. Kravet
   er eksplicitte location-blokke — hvilket samtidig gør nginx.conf til den eneste præcise
   beskrivelse af systemets offentlige overflade, hvilket der ikke findes i dag.
3. **En perimeter er ikke en lukning før service-portene lukkes.** 8001–8012 bliver på
   `0.0.0.0` af denne ADR alene. At lukke dem brækker `tests/e2e/conftest.py`, hvis
   `_HEALTH_ENDPOINTS` poller **otte** porte direkte (8001–8006, 8010, 8012) — den skal have
   en vej ind først, ellers bliver E2E rød i CI. Bemærk at listen ikke er identisk med
   browserens ti origins: den mangler ai (8007), notification (8008) og banking (8009), og den
   *indeholder* analytics (8012), som browseren aldrig taler med direkte. Perimeterens
   offentlige overflade og e2e's antagelser om nåelighed er altså to forskellige mængder, og
   begge skal opgøres når portene lukkes.
4. **nginx.conf går fra 12 til ~60 linjer, og intet bevogter den mod drift.**
   `scripts/compose_check.py` kender ikke nginx, så en ny service kan tilføjes uden en
   proxy-regel og fejle først i browseren. En femte regel dér er den naturlige plads.

**Hvad vi accepterer:** nginx bliver et single point of failure for frontendens API-adgang.
Det er acceptabelt, fordi den allerede er det for selve app-bundlen — en nede nginx betyder
ingen frontend uanset. Vi flytter ikke risikoen, vi undlader at tilføje en ny.

**Hvad denne ADR *ikke* løser:** credentials. `guest:guest` på RabbitMQ,
`xpack.security.enabled: "false"` på ES og Postgres-passwords i klartekst i compose er urørte,
og alt der kører *på* maskinen når stadig datastores uden auth. Perimeteren handler om
browser-trafik, ikke om at hærde datastores.

---

## Implementeret 2026-07-28 (P3-43)

Fem commits, `4d73b527`..`cd9b94fb`. Formen holdt; syv ting måtte måles frem, og de fire
første er afvigelser fra det ADR'en beskrev:

1. **En denyende `location /api/ { return 404; }` blev tilføjet** — punkt 2 sagde "eksplicitte
   location-blokke, ingen catch-all" og stoppede dér. Det var utilstrækkeligt: en
   ikke-allowlistet `/api/`-sti faldt ned i SPA-fallbacken og svarede **200 + index.html**.
   `/api/v1/internal/accounts/1/exists` og `/api/v1/categorize/` var altså ikke eksponeret,
   men de *så* ud som om de virkede. Backstoppen er det modsatte af en catch-all: den
   proxyer intet, den nægter. Efter: 404 `text/html` fra nginx.
2. **`proxy_set_header Host $http_host`, ikke `$host`.** `$host` stripper porten, og FastAPI
   bygger sin trailing-slash-redirect ud fra Host, så `/api/v1/accounts` svarede
   `Location: http://127.0.0.1/api/v1/accounts/` — port 80, hvor intet lytter. Syv af seksten
   ruter giver 307, og `crudFactory` kalder accounts/goals uden trailing slash.
3. **`client_max_body_size` hævet til 11m på transactions-locationen.** nginx' default er 1 MB
   mod `CSV_MAX_BYTES` på 10 MiB. Målt efter: en 10,5 MiB-fil får **servicens** danske besked
   (`Forespørgslen er for stor (grænsen er 10 MB).`), ikke nginx' HTML-413. Det var hensigten
   med at vælge 11 og ikke 10.
4. **Punkt 2's ordlyd om `/api/v1/users/{id}`.** ADR'en nævnte kun account og
   categorization som `INTERNAL_API_KEY`-vogtede. `GET /api/v1/users/{user_id}` er det også,
   men ligger ikke under et `/internal/`-segment, og søskenden `/api/v1/users/me` gør et
   præfiks-`deny` umuligt. Accepteret på den offentlige overflade, dokumenteret i nginx.conf,
   og flytningen er **P3-44**. En regex-`deny` blev fravalgt fordi den ville skabe en
   ordningsafhængighed i nginx.conf som ingen test fanger når den brydes.

Tre ting der ikke ændrer formen, men er værd at kende:

5. **Punkt 4's rule 5 findes** (`scripts/compose_check.py`), med fire assertions verificeret
   røde hver for sig — elleve kontroller i alt. Reglen fejler også når en assertion er
   *uafgørlig* (upstream uden `ports:`, `location` med modifier), fordi en sprunget assertion
   læses som en bestået.
6. **nginx cacher upstream-IP'er ved config-load.** Samme egenskab der gør `depends_on` til et
   krav gør en genskabt container til 502 på alle ruter indtil `restart frontend`. → **P3-45**,
   hvor byttet (dynamisk genopslag mod tab af `nginx -t`-validering) er skrevet ned.
7. **De 11 `CORSMiddleware` er væk, målt frem for aflæst.** Ingen test asserterer på
   CORS-headers, så suiten kunne ikke bevise det. Preflight direkte mod alle 11 porte:
   før 200 + `access-control-allow-origin` på en tilladt origin, efter 405 uden headers.
   Sidefund: `pydantic-settings` kører `extra='forbid'`, så en forældet `CORS_ORIGINS`-linje
   i en `.env`-*fil* nu dræber servicen ved import (env-vars ignoreres derimod).

**Punkt 3 står uændret:** service-portene 8001–8012 er stadig på `0.0.0.0`. `make test-e2e`
giver 24 grønne netop fordi den rammer dem direkte. Perimeteren er en tilføjet vej, ikke en
lukket dør.
