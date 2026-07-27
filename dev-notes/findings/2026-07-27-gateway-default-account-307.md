---
title: "Gatewayens default-konto-opslag ramte en 307 og returnerede altid None — fallback-stien har været død"
date: 2026-07-27
severity: MEDIUM
area: gateway
status: resolved
resolved-by: f71ef50e
---

# Gatewayens default-konto-opslag ramte en 307 og returnerede altid `None`

**Hvor**: `services/gateway-service/app/auth.py`, `get_account_id_from_headers`'
gren for "ingen `X-Account-ID`-header".

**Defekt**: Gatewayen kaldte account-service på `/api/v1/accounts` uden trailing
slash. Account-service ruter `/api/v1/accounts/`, så FastAPI svarede **307
Temporary Redirect** — og `httpx` følger ikke redirects medmindre man beder om
det. Betingelsen `if resp.status_code == 200` var dermed aldrig sand, funktionen
faldt igennem til `return None`, og resolveren rapporterede
`"Account ID required. Send Authorization and/or X-Account-ID header."`
selvom kalderen havde sendt et fuldt gyldigt `Authorization`-header.

Verificeret inde fra gateway-containeren:

```
http://account-service:8003/api/v1/accounts   -> 307
http://account-service:8003/api/v1/accounts/  -> 401   (dvs. ruten svarer)
```

**Hvorfor ingen bemærkede det**: frontenden sender altid `X-Account-ID` og rammer
derfor den *anden* gren, som bruger `/api/v1/accounts/{account_id}` og ikke har
problemet. Kun fallback-adfærden — "ingen header → brug brugerens første konto" —
var påvirket, og den havde ingen kaldere i praksis. Fejlbeskeden er desuden
vildledende: den beder om et header som kalderen allerede havde sendt. Det
matcher [[project_live_verify_gateway_auth]]'s note om at fejlen lyver.

**Fundet**: under P1-15's live-verifikation af `require_exp`. Ved probing af
gatewayens to decode-stier fejlede `_decode_user_id`-stien for *begge* tokens —
også det gyldige — hvilket ikke kunne forklares af `require_exp` og derfor
pegede på noget længere nede.

**Rettelse**: trailing slash på URL'en. Valgt frem for `follow_redirects=True`,
fordi den eksplicitte sti ikke får gatewayen til at følge vilkårlige redirects
fra en intern service.

**Verificeret efter rettelse**: GraphQL-query uden `X-Account-ID` returnerer nu
data med et gyldigt token, og afvises fortsat med et token uden `exp`.

**Lære**: en gren der altid returnerer `None` ser ud som "ikke konfigureret"
snarere end "i stykker". At `if status == 200` fejler stille er værre end en
exception — overvej at logge den uventede statuskode i den slags
best-effort-stier, så de ikke kan dø tavst.
