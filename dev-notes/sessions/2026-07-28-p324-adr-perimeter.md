# Session — 2026-07-28 · P3-24's ADR-halvdel

**Leveret:** [ADR-0005](../../docs/adr/0005-nginx-as-security-perimeter.md) +
[decision-note](../decisions/2026-07-28-nginx-as-perimeter.md). Ingen kode — beslutning alene,
efter aftale. Implementeringen er nyoprettet **P3-43**.

## Beslutningen

**Frontendens nginx er perimeteren, ikke gateway-service.** Browseren taler med én origin;
nginx `proxy_pass`'er per path over compose-netværkets interne DNS. Gateway-service forbliver
CQRS-læsesiden.

## Hvad undersøgelsen ændrede ved spørgsmålet

Sweepets SEC-3 stillede det som "browseren taler med ti origins". Fire målinger viste at det
var en ufuldstændig framing:

1. **Gatewayen er ikke en proxy.** `main.py` monterer `/health`, en saga-router og GraphQL.
   Writes går allerede uden om den. "Skal gatewayen være perimeter" var altså ikke et spørgsmål
   om at *udvide* en rolle, men om at give den en helt ny.
2. **De ti origins er ikke konfigurerbare.** `serviceUrls.js` læser `VITE_*` med
   `localhost:800X` som fallback — og de vars er ikke sat nogen steder, hverken i compose eller
   k8s. Der er heller ingen vite dev-proxy. Fallbacks er altså det der bygges ind i imaget.
3. **k8s har ingen indgang overhovedet.** 30 ClusterIP-Services, ingen Ingress, ingen NodePort,
   ingen LoadBalancer. Adgang sker via `scripts/k8s-port-forward.sh`, som gendanner de samme
   localhost-origins.
4. Deraf: **der findes ikke en deployment hvor en perimeter ville være nåelig.** ADR'en
   forpligter en form, mens der endnu intet er at bryde. Det er en behageligere position end
   sweepet antydede — og den er værd at skrive ned, fordi den forsvinder i det øjeblik nogen
   laver en Ingress.

## Hvorfor ikke de to andre

**Gateway som perimeter** ville lægge en Python-hop foran hver write og gøre CQRS-læsesiden til
skrive-chokepunkt, mod at ruter-tabellen skulle vedligeholdes i FastAPI-kode frem for i den
komponent der allerede står i trafikkens vej. Den eneste reelle fordel — auth ét sted — er
unødvendig, fordi hver service allerede validerer JWT selv.

**Multi-origin** blev afvist på at det ikke er gratis, hvilket var fristelsen. Det koster
allerede 11 `CORSMiddleware` i sync, blokerer HttpOnly-cookie definitivt, tvinger P2-27 til N
implementeringer og efterlader P3-25's CSP delvis. Løbende pris, engangs besparelse.

## Fire fælder målt frem, så P3-43 ikke opdager dem

1. **SSE brækker på nginx' default.** `ai-service`s `/api/v1/chat/stream` returnerer
   `EventSourceResponse`. Kræver `proxy_buffering off` + hævet `proxy_read_timeout`.
2. **Positiv allowlist, ikke catch-all.** `/api/v1/internal/*` (account) og `/api/v1/categorize`
   (categorization) er `INTERNAL_API_KEY`-vogtede. En `location /api/`-catch-all ville
   publicere dem. Bonus: eksplicitte blokke gør nginx.conf til den første præcise beskrivelse
   af systemets offentlige overflade.
3. **Perimeteren lukker ikke service-portene.** 8001–8012 bliver på `0.0.0.0`.
4. **Intet bevogter nginx.conf mod drift** — `compose_check.py` kender den ikke.

## Én påstand jeg skrev og selv måtte rette

Jeg skrev først i ADR'en at e2e's health-gate "poller alle ti direkte". Tjekket:
`_HEALTH_ENDPOINTS` har **otte** (8001–8006, 8010, 8012). Den mangler ai, notification og
banking, og den *indeholder* analytics — som browseren aldrig taler med, og som derfor ikke er
en af de ti origins. Perimeterens offentlige overflade og e2e's nåeligheds-antagelser er to
forskellige mængder. Rettet i ADR'en, og det er nu en eksplicit del af fælde 3.

**Og pipe-fælden dukkede op igen** — `make notes-check 2>&1 | tail -3` viste kun
"See the dev-notes skill", ikke det egentlige problem (decision-noten manglede i 00-INDEX.md).
Kørt uden pipe, fik den rigtige linje. Samme dag som den blev noteret i standing traps for
sjette gang.

## Open ends

- **P3-43** er oprettet med alle fire fælder i detail-sektionen. Oplåser P3-25 og P2-27.
- **P2-27's placering er nu afgjort** (`limit_req`-zone i nginx), men forudsætter P3-43.
- **Credentials hører ikke til perimeteren** og er stadig urørte.
- CI ikke kørt på docs-commit; det er ren markdown.
