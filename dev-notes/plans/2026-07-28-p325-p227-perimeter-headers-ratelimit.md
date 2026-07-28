---
title: P3-25 + P2-27 — security headers og limit_req-zone i perimeteren
date: 2026-07-28
status: done
backlog-items: [P3-25, P2-27, P1-16]
related:
  - ../../docs/adr/0005-nginx-as-security-perimeter.md
  - ../plans/2026-07-28-p343-nginx-perimeter.md
  - ../findings/2026-07-26-product-surface-sweep.md
---

# P3-25 + P2-27 — security headers og limit_req-zone i perimeteren

## Goal

Perimeteren fra P3-43 begynder at gøre andet end at route. Én `server`-blok får de fire
security headers browseren faktisk håndhæver, og login/register får en `limit_req`-zone, så
der findes en bremse på de to uautentificerede ruter i systemet.

Færdig når: (a) CSP'en er **bevist håndhævet af browseren**, ikke kun leveret — verificeret
ved at et bevidst stramt direktiv giver en violation i konsollen og en synligt brækket
dialog; (b) headerne er til stede på **både 200 og 404**, altså også på deny-backstoppen;
(c) 20 hurtige login-POSTs gennem `:3000` giver 429 efter bursten, mens **de samme 20 direkte
mod `:8001` alle passerer** — omgåelsen målt og skrevet ned frem for underforstået; og (d)
`limit_req` er verificeret **rød** ved at fjerne direktivet.

De to items ligger i én plan fordi de rører samme `server`-blok i samme fil. Splittet ville
koste to gange den samme verifikationsrunde — og verifikationen er langt det dyreste her,
fordi den kræver en browser i hånden.

## Context

P3-43 byggede stedet disse to skulle bo, og STATUS.md kalder dem derfor backloggens
billigste items. Det holder for *koden*. Det holder ikke for beviset, og det er hele grunden
til at denne plan er så lang: **begge items har en fejlmode hvor headeren/direktivet er
leveret korrekt og alligevel ikke beskytter noget.**

**Seks målinger fra sweepet før planen. De ændrer scopet, og ingen af dem står i backloggen:**

1. **CSP-niveauet kan afgøres på bundlet frem for på skøn.** I `build/assets/index-*.js`:
   **0** `eval(`, **0** `new Function` → `script-src 'self'` holder *uden* `'unsafe-eval'`.
   Men **1** `createElement("style")` (radix' scroll-lock eller recharts) plus **35**
   `style={{…}}` i `src/` → `style-src` **skal** have `'unsafe-inline'`. Videre: **0**
   `data:`/`blob:`-URI'er, **0** `url()` i den byggede CSS, **0** `new Worker`, og de
   https-strenge der er i bundlet er doc-links i fejlbeskeder plus SVG-namespacet
   `www.w3.org` — ingen af dem er fetch-mål. `default-src 'self'` er derfor målt, ikke antaget.
2. **`build/` er fra 26. juli, altså før P3-43.** Det gamle bundle indeholder stadig
   `http://localhost` fra de dengang absolutte `serviceUrls.js`. Målingerne ovenfor er
   strukturelt gyldige, men **skal gentages på et friskt build** før CSP'en låses — ellers
   er `connect-src 'self'` verificeret mod en artefakt der ikke findes i imaget længere.
3. **`add_header` gælder som default ikke fejl-svar.** nginx sætter kun headeren på en
   hvidliste af statuskoder (200, 201, 204, 206, 3xx). Deny-backstoppen `location /api/ {
   return 404; }` er en af de vigtigste responses at have headers på, og den ville stå uden.
   Derfor `always` på alle fire — ikke som forsigtighed, men fordi den ellers mangler præcis
   dér hvor filen er mest eksplicit om at være en perimeter.
4. **`add_header` nedarves kun til en `location` der ikke selv sætter én.** Filen har i dag
   **0** `add_header`, så nedarvning til alle 17 locations virker. Men den dag en location
   får sin egen — fx en `Cache-Control` på assets, som P3-28 vil gøre — **forsvinder alle
   fire security headers i den location, tavst.** Det er samme fejlmode som rule 5 findes
   for. Se **Åbne valg**.
5. **`=`-modifier er forbudt af rule 5.** `parse_nginx` (`scripts/compose_check.py:302-309`)
   rapporterer enhver `location` med modifier som et *problem*, med begrundelsen "it would
   pass without having checked anything". Login-ruten skal derfor være en **præfiks**-location
   `location /api/v1/users/login` — hvad der virker fint, da nginx vælger længste match og
   præfikset er længere end `/api/v1/users`. Alternativet er at lære rule 5 modifier-semantik
   først, hvad der er et større stykke arbejde end selve itemet.
6. **`$remote_addr` er 192.168.65.1 for al host-trafik.** Målt i frontendens access-log:
   Docker Desktops gateway-IP, ikke klientens. **`limit_req_zone $binary_remote_addr`
   kollapser altså til én global bucket i denne deployment.** To konsekvenser: grænsen skal
   være rummelig nok til ikke at låse den legitime enebruger ude, og en test der hamrer fra
   hosten **kan ikke bevise per-IP-isolation** — den kan kun bevise at *en* bucket findes.
   Kontrollen for det skal køres fra en sibling-container, som har sin egen IP på
   compose-netværket.

**Og det ubehagelige, som bør stå i planen frem for at blive opdaget:** `tests/e2e/` rammer
service-portene direkte — det er derfor `make test-e2e` var upåvirket af hele P3-43. Den
samme egenskab gør at **vores egen e2e-suite er beviset på at rate-limiteren er omgåelig.**
Det er ikke en fejl i suiten; det er trusselmodellen der er "den browser-vendte overflade",
og ADR-0005 punkt 3 sagde det på forhånd. Men det betyder at P2-27 ikke lukker
brute-force-vektoren — den lukker den *for browseren*.

## Non-goals

- **Service-portene 8001–8012 lukkes ikke.** Uændret fra ADR-0005 punkt 3. Både headers og
  rate limits gælder browser-trafik; enhver der rammer en port direkte møder ingen af dem.
  Perimeteren er stadig en tilføjet vej, ikke en lukket dør.
- **HSTS medtages ikke.** Målt: `grep -rn "listen 443\|ssl_certificate"` → **0 hits** i hele
  repoet. Der er ingen TLS nogen steder, og browsere ignorerer `Strict-Transport-Security`
  leveret over HTTP per spec. Headeren ville være inert — og en inert header læses som
  dækning ved næste audit. Den hører til den dag der findes en TLS-terminering; noteret i
  P3-25's backlog-rubrik frem for i filen.
- **JWT'en flytter ikke til en HttpOnly-cookie**, og de PII-claims (`username`, `email`) der
  ligger i `localStorage` bliver liggende. Begge er egne items; CSP'en reducerer *risikoen*
  ved dem uden at røre dem. Bemærk at der stadig er **ingen XSS-sink** i `src/` — ingen
  `dangerouslySetInnerHTML`, `innerHTML` eller `eval` — så dette er defence in depth.
- **Password-politik, lockout og 409-eksistensleak i `register` ændres ikke.** P2-27's
  rubrik nævner alle tre. De kræver domæne-beslutninger (og `register`-leaket kræver at man
  vælger mellem to dårlige svar); rate-limiten gør enumeration *dyrere* uden at afgøre dem.
- **`slowapi` introduceres ikke nogen steder.** Besluttet 2026-07-28: zonen i perimeteren,
  hullerne navngivet. Bælte-og-seler ville betyde to steder at holde grænsen i sync.
- **Ingen adfærdsændring i nogen service.** Kun `services/frontend/nginx.conf` røres af
  koden i trin 1–2.

## Steps

1. [ ] **Genbyg frontenden og gentag CSP-målingerne mod det friske bundle.**
   `npm run build` i `services/frontend`, derefter samme fire greb som i Context punkt 1 mod
   de nye `build/assets/index-*.{js,css}` — `eval(`, `new Function`,
   `createElement("style")`, `url(`, `data:`, eksterne hosts. Ingen commit. Formålet er at
   afvise punkt 2's forbehold: hvis `http://localhost` stadig optræder, er `connect-src
   'self'` forkert og trin 2 skal ændres, ikke debugges bagefter.

2. [ ] **Commit 1 (P3-25): fire security headers i `server`-blokken.**
   `services/frontend/nginx.conf`, umiddelbart efter `client_max_body_size`-blokken, før
   deny-backstoppen. Alle fire med `always` (Context punkt 3). Diff-formen er fire
   `add_header`-linjer plus den kommentar der bærer *hvorfor* hvert direktiv har den værdi
   det har — filen er efter P3-43 den eneste præcise beskrivelse af den offentlige overflade,
   og et CSP-direktiv uden begrundelse bliver løsnet af den næste der møder en violation:

   ```
   add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
   add_header X-Content-Type-Options "nosniff" always;
   add_header X-Frame-Options "DENY" always;
   add_header Referrer-Policy "no-referrer" always;
   ```

   `'unsafe-inline'` står **kun** på `style-src`, og kommentaren skal navngive målingen der
   tvang den (det ene `createElement("style")` + de 35 `style={{}}`) — ellers ser den ud som
   slendrian. `frame-ancestors 'none'` og `X-Frame-Options: DENY` er bevidst overlappende:
   den første er den der gælder, den anden er for browsere der ikke læser den første.
   `no-referrer` er gratis her, fordi der ikke findes en ekstern destination at sende en
   referer til.

3. [ ] **Commit 2 (P2-27): `limit_req`-zone på login og register.**
   Samme fil. `limit_req_zone` skal ligge i **http-kontekst** — altså i toppen af filen,
   *uden for* `server`-blokken; det virker fordi Dockerfilen kopierer filen til
   `/etc/nginx/conf.d/default.conf`, som nginx inkluderer inde fra `http`. Derefter to nye
   præfiks-locations (ikke `=`, Context punkt 5), hver med `proxy_pass
   http://user-service:8001` gentaget, fordi længste-match betyder at de ikke længere
   nedarver fra `/api/v1/users`:

   ```
   limit_req_zone $binary_remote_addr zone=auth:10m rate=10r/m;
   limit_req_status 429;
   ```
   ```
   location /api/v1/users/login    { limit_req zone=auth burst=5 nodelay; proxy_pass http://user-service:8001; }
   location /api/v1/users/register { limit_req zone=auth burst=5 nodelay; proxy_pass http://user-service:8001; }
   ```

   `limit_req_status 429` fordi nginx' default er **503**, hvad der er den forkerte
   diagnose at give en klient. `rate=10r/m burst=5 nodelay` er valgt mod Context punkt 6:
   med én global bucket skal en enkelt legitim bruger der taster forkert kunne blive ved,
   og fem på stribe plus én hver sjette sekund rækker. Tallet er det mest oplagte at have
   valgt forkert — kommentaren skal sige hvad man skruer på og hvorfor, ikke bare hvad der
   står. Register er med, fordi 409-eksistensleaket derved bliver dyrt at høste selvom
   selve leaket er et non-goal.

4. [ ] **`make compose-check` — rule 5 skal stadig være grøn med to nye locations.**
   Begge nye upstreams peger på `user-service:8001`, som rule 5's assertion 1 verificerer
   mod compose. Kør den *før* verifikationen nedenfor: er den rød på en modifier eller en
   port, er der ikke noget at måle endnu.

5. [ ] **Verifikation, HTTP-niveau — headers på både 200 og 404.**
   `curl -i http://127.0.0.1:3000/` for SPA-svaret og `curl -i
   http://127.0.0.1:3000/api/v1/nonexistent` for deny-backstoppen; begge skal have alle
   fire headers. Det andet kald er det der beviser `always` (Context punkt 3). Bekræft i
   `docker logs finance-tracker-frontend-1` at nginx faktisk talte requesten — P3-43's
   første rute-måling ramte en Vite dev-server på `[::1]:3000` og gav plausible svar fra den
   forkerte komponent. **Brug `127.0.0.1`, ikke `localhost`.**

6. [ ] **Verifikation, browser — CSP'en håndhævet, med kontrol.** Dette er trinnet der
   faktisk afgør P3-25, og det kan ikke automatiseres i dette repo: de 344 frontend-tests
   kører i jsdom, som **ikke håndhæver CSP**, og der er ingen Playwright. De ville være
   grønne under en CSP der brækker appen — nøjagtig samme blindhed som da de bestod med
   P3-43's URL-fejl genindført, fordi de mocker `fetch`.
   - **Treatment:** driv login → dashboard (recharts tegner) → åbn en radix-dialog
     (scroll-lock injicerer `<style>`) → CSV-import, med DevTools-konsollen åben. Nul
     CSP-violations, appen intakt.
   - **Kontrol:** stram `style-src` til `'self'` (fjern `'unsafe-inline'`), reload, og
     bekræft at konsollen **rapporterer en violation** og at dialogen/grafen brækker synligt.
     Sæt tilbage. Uden dette trin har vi kun bevist at en header leveres — ikke at browseren
     håndhæver den, og en CSP der ikke håndhæves ser identisk ud med en der gør.

7. [ ] **Verifikation, rate limit — treatment plus tre kontroller.**
   Alle med `rc=$?` læst eksplicit; **ingen pipe gennem `head`/`tail`** (fælden ramte igen i
   P3-24's kontrol, hvor en kontrol var ét sekund fra at blive noteret som bestået uden at
   være kørt).
   - **Treatment:** 20 hurtige `POST /api/v1/users/login` mod `:3000` → de første ~5 slipper
     igennem, resten **429**. Optæl statuskoderne.
   - **Kontrol A, omgåelsen:** de samme 20 direkte mod `127.0.0.1:8001` → **nul 429**. Det
     er beviset på hvad itemet ikke dækker, og det hører i Outcome.
   - **Kontrol B, per-IP:** samme 20 fra en sibling-container på compose-netværket
     (`docker run --rm --network <compose-net> curlimages/curl …`), *mens* hostens bucket er
     opbrugt → den skal have sin egen. Det er det eneste greb der kan skelne per-IP fra
     global (Context punkt 6). Bekræft de to forskellige `$remote_addr` i access-loggen.
   - **Kontrol C, verificeret rød:** fjern `limit_req`-linjen fra login-locationen, reload
     nginx, 20 requests → **20 passerer**. Sæt tilbage.
   - **Afgrænsning:** hamr `/api/v1/transactions` og bekræft **nul 429** — zonen må ikke
     have lækket ud over de to auth-ruter.

8. [ ] **`make test-e2e` (forventet 24 passed) og frontendens `npm test` (344).**
   Begge forventes **upåvirkede**, og det er vigtigt at sige hvorfor de derfor ikke er
   evidens: e2e rammer portene direkte (og demonstrerer dermed Kontrol A), og
   frontend-testene håndhæver ikke CSP. De kører som regressions-net for at intet *andet*
   knækkede, ikke som bevis for planen.

9. [ ] **Commit 3: noter.** Plan-Outcome med de faktiske tal, session-log,
   `backlog/BACKLOG.md`-rækkerne til `done 2026-07-28` med link hertil, HSTS-udeladelsen
   noteret i P3-25's rubrik, STATUS.md's Active/Next up, og `00-INDEX.md`.
   `make notes-check` før commit.

## Åbne valg

- **Skal `add_header`-skyggen vogtes af en rule 6?** Context punkt 4: filen har 0
  `add_header` i dag, så nedarvning virker — men den første location der sætter sin egen
  header taber alle fire security headers tavst, og P3-28 (gzip + `Cache-Control: immutable`
  på assets) er præcis det item der vil gøre det. En regel der kræver at enhver location med
  `add_header` gentager de fire, er ~15 linjer i `compose_check.py`. **Anbefaling: eget
  item, ikke dette.** Grunden er at STATUS.md allerede skylder en omdøbning af "build
  hygiene" og P2-21 vil have en rule 6 til compose-vs-kustomization-diffen; at afgøre
  regel-nummerering og filnavn som bivirkning af et S-item er hvordan man ender med et navn
  der ikke passer. Men risikoen skal skrives ned i dag, ellers findes den kun i denne plan.
- **`rate=10r/m` er et gæt indtil andet er målt.** Med én global bucket (Context punkt 6) er
  der ingen måling der kan retfærdiggøre tallet uden en rigtig flerbruger-belastning, som
  ikke findes. Det er valgt konservativt-rummeligt. Hvis trin 7's treatment viser at et
  normalt login-flow rammer grænsen, er det tallet der er forkert — ikke formen.

## Risks & rollback

- **Den farligste fejlmode er en CSP der brækker appen i browseren mens alt grønt i repoet
  bliver ved med at være grønt.** Detektion: trin 6's manuelle gennemgang er det eneste
  instrument. Mitigering hvis den bliver ustabil: skift headeren til
  `Content-Security-Policy-Report-Only` — så håndhæves intet, violations logges stadig i
  konsollen, og appen kan ikke brække. Bemærk at der ikke findes et report-endpoint, så
  konsollen er hele rapporteringen.
- **Rate-limiten kan låse en demo ude**, fordi bucket'en er global på denne maskine. Symptom:
  429 på login uden at nogen har hamret. Rollback er én linje (fjern `limit_req` fra de to
  locations) eller at hæve `rate`.
- **Rollback er per commit** og rører kun `nginx.conf`: `git revert` af commit 2 fjerner
  rate-limiten, af commit 1 headerne. Ingen migration, intet schema, ingen service-kode,
  ingen dependency. Genstart er `docker compose restart frontend` — men bemærk P3-43's
  fund: **nginx slår upstream-navne op ved config-load**, så en frontend der ikke starter
  efter en ændring kan skyldes en manglende upstream-container og ikke ændringen.
- **`nginx -t` før reload.** En syntaksfejl i `limit_req_zone` (forkert kontekst er den
  oplagte) gør at containeren ikke starter, hvad der ser ud som "hele appen er nede".

## Outcome

Landet 2026-07-28 i fire commits. **Planen forudsagde to; den tredje og fjerde er hele
historien.**

| Commit | Hvad |
|---|---|
| `38634dca` | P3-25: fire security headers med `always` |
| `68dc3db0` | **P1-16**: absolut GraphQL-URL — en HIGH-regression fundet af P3-25's kontrol |
| `e377a420` | Rettelse af CSP-begrundelsen i `38634dca`, som målingen modsagde |
| `474b9643` | P2-27: to `limit_req`-zoner på login og register |

### Det vigtigste udfald var ikke et af de to items

**P3-25's kontrol afdækkede at P3-43 havde brækket hele GraphQL-læsestien i browseren.**
`graphql-request` kalder `new URL(url)` uden base, så den relative sti fra `c0418646` kastede
`TypeError: Invalid URL`, og dashboard, transaktioner og kategorier viste
`Fejl: Failed to construct 'URL': Invalid URL` i stedet for data. Se
[findings/2026-07-28-graphql-client-rejects-relative-url.md](../findings/2026-07-28-graphql-client-rejects-relative-url.md)
og **P1-16**.

Vejen dertil er argumentet for at trin 6 ikke var overdrevet: CSP'en kunne kun verificeres
ved at *drive appen* i en rigtig browser-engine, og for at nå en side med inline styles måtte
der seedes en autentificeret session. Ingen leden efter denne bug fandt den. Kravet om at
drive appen gjorde. **`curl` kunne aldrig have set den — den kører ikke klienten** — og de 344
frontend-tests var blinde ved konstruktion, fordi `graphqlClient.test.jsx:12` mocker
`GraphQLClient` væk. Målt som kontrol: med regressionen genindført fejler **kun de to nye
tests**, mens de fire mockede bliver grønne.

### P3-25: hvad der blev målt, og hvad der blev korrigeret

Headerne sidder på **200, 404 og et proxyet 422** — de to sidste er `always`-beviset, da
ingen af dem er på nginx' default-hvidliste. Alle tre bekræftet i access-loggen som talt af
nginx (`127.0.0.1`, ikke `localhost`, jf. P3-43's Vite-fælde).

CSP'en er **bevist håndhævet, ikke kun leveret.** Kontrol C1 (`script-src 'none'`): violation
logget *og* React mountede ikke (742 bytes mod 1802). Det er forudsætningen for at treatments
0 violations betyder noget — ellers målte jeg med et instrument der ikke kunne se en fejl.

**Planens punkt 1 indeholdt en fejlslutning, som kontrollen fangede.** Jeg skrev at
`'unsafe-inline'` var tvunget af *både* `createElement("style")` og de 35 `style={{…}}`. Kun
den første holder. Målt isoleret, side om side under samme politik:

- Reacts vej (CSSOM, `element.style.x = y`, som `style={{}}` kompilerer til) →
  **0 violations** under `style-src 'self'`, og style-attributten står i DOM'et alligevel.
  CSP rører ikke CSSOM.
- `react-remove-scroll`s vej (`createElement("style")` + `appendChild(createTextNode(...))`)
  → **1 violation**: `"Applying inline style violates ... 'style-src 'self''"`.

Direktivet er altså uændret nødvendigt — men af én grund, og den fyrer kun når en dialog
mounter. **Det er også derfor C2 ikke fyrede på hverken login eller dashboard: proben klikker
ikke.** Mekanismen blev derfor bevist isoleret frem for i appen; det er en svagere form, og
det står i `nginx.conf` som sådan.

Undervejs bekræftet at `build/` fra 26. juli var et ugyldigt målegrundlag (planens punkt 2):
`http://localhost` var stadig i det friske bundle, men opklaret til react-routers
SSR-fallback-base, ikke et fetch-mål — så `connect-src 'self'` holder.

### P2-27: målingen ændrede konfigurationen

Treatment: **6 igennem på en frisk zone** (1 + burst 5), derefter 429 — nginx' dokumenterede
opførsel. Verificeret rød: `limit_req` fjernet → 20/20 passerer. Afgrænsning: 20 × `/users/me`
og 20 × `/transactions/` → 20/20 × 200, så præfiks-præcedensen rammer kun de to ruter.

**Første treatment-måling var forurenet af mig selv.** Den viste 2 igennem i stedet for 6,
fordi et fejlet zsh-forsøg (`declare -A` virker ikke der) havde afsendt requests *før* det
fejlede og drænet bucket'en. Målt igen på en frisk zone → præcis 6. Fælden er ikke ny — den er
"instrumentet kan være blindt" i endnu en form: **en fejlet kommando kan have haft bivirkninger
inden den fejlede.**

**Planen foreskrev én zone. Målingen tvang to.** Med fælles zone gav 12 × register
6 × 409 + 6 × 429, hvorefter login svarede **429 med det samme** — de delte bucket. Sammen med
den globale bucket betyder det at nogen der hamrer register kan spærre alles login: en
selv-DoS-sti indført af bremsen selv. Efter opdelingen, målt: register 429, login 401.

Punkt 6's forbehold holdt: `$remote_addr` er `192.168.65.1` for al host-trafik. Per-IP blev
bevist alligevel via kontrol B, og den skulle strammes for at gælde — første forsøg gav 401 til
begge, fordi der var gået 18s og tokens var genopfyldt. Med hostens bucket faktisk opbrugt:
host **429**, sibling **401**, host straks efter stadig **429**, og to nøgler i access-loggen
(`192.168.65.1`, `172.18.0.54`).

**Omgåelsen er målt, ikke underforstået:** de samme 20 requests direkte mod `:8001` gav
20 × 401 uden en enkelt 429.

### Regressions-nettet

`make test-e2e` **24 passed**, frontend **346 passed** (344 + de to nye), lint grøn,
`make compose-check` grøn (20 locations, 18 upstreams). Begge suiter var forventet upåvirkede,
og det er præcis derfor de ikke er evidens: e2e rammer portene direkte (og demonstrerer dermed
omgåelsen), og jsdom håndhæver ikke CSP.

Sluttilstand i browseren: dashboardet render **24.412 bytes** med rigtige aggregerede tal, 0
CSP-violations, ingen URL-fejl.

### Follow-ups

- **P3-47** — `add_header`-skyggen. Uændret vurdering fra **Åbne valg**: eget item. Risikoen
  står nu i `nginx.conf` med reference.
- **HSTS** forbliver udeladt indtil der findes en TLS-terminering; noteret i P3-25's rubrik.
- **`rate=10r/m` er stadig et valg uden belastningsmåling bag.** Uændret fra Åbne valg.
- **C2-kontrollen mangler stadig sin app-nære form.** At bevise `'unsafe-inline'` *i appen*
  kræver at en radix-dialog åbnes, altså et klik — hvad der kræver browser-automatisering
  repoet ikke har. Det er det stærkeste argument der er kommet for at anskaffe det: dette
  items ene ægte fund kom fra en browser, og den næste ville kræve et klik.
