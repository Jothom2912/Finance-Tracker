# Session — P3-25 + P2-27, og den regression de afdækkede (2026-07-28)

Fire commits på `master`: `38634dca` (security headers), `68dc3db0` (**P1-16**, GraphQL-URL),
`e377a420` (rettelse af CSP-begrundelsen), `474b9643` (rate limit). Kun `nginx.conf`,
`graphqlClient.jsx` og én ny testfil er rørt.

Planen: [2026-07-28-p325-p227-perimeter-headers-ratelimit.md](../plans/2026-07-28-p325-p227-perimeter-headers-ratelimit.md).
Alle tal og kontroller står i dens **Outcome** — dette er historien om hvordan det gik.

## Det der gør sessionen værd at læse

**Det vigtigste fund tilhørte ingen af de to items.** P3-25's CSP-kontrol krævede at appen blev
*drevet* i en rigtig browser-engine, fordi jsdom ikke håndhæver CSP. For at nå en side med
inline styles måtte jeg seede en autentificeret session — og dér stod dashboardet med
`Fejl: Failed to construct 'URL': Invalid URL` i stedet for data. **P3-43 havde brækket hele
GraphQL-læsestien nogle timer tidligere, samme dag.**

Kæden af tavsheder er sessionens egentlige indhold:

- `curl` verificerede GraphQL same-origin i P3-43, og det var **sandt om transporten**. nginx
  proxyer korrekt. `curl` kører bare ikke klienten, og fejlen var i klienten.
- De 344 frontend-tests var **blinde ved konstruktion**: `graphqlClient.test.jsx:12` mocker
  `GraphQLClient` væk. Bevist frem for påstået — med regressionen genindført fejler kun de to
  nye tests, mens de fire mockede bliver grønne.
- Ingen leden fandt den. **Kravet om at drive appen fandt den.**

## Fem gange hvor målingen modsagde det jeg skrev

Rækkefølgen er kronologisk, og de er ikke ens i alvor.

1. **`build/` var et ugyldigt målegrundlag.** `http://localhost` var stadig i det friske bundle
   efter P3-43. Planen havde forudset forbeholdet, så det blev opklaret frem for debugget:
   react-routers SSR-fallback-base, ikke et fetch-mål.
2. **Min kontrol af en mutation aflæste den forkerte linje.** `grep -o "script-src [^;]*" |
   head -1` ramte kommentarblokken, ikke `add_header`, så begge mutations-diffs var tomme og så
   ud som om `sed` havde fejlet. Den havde virket. **En kontrol kan være forkert i den ende der
   læser, ikke kun i den der skriver.**
3. **`'unsafe-inline'`-begrundelsen var halvt forkert, og jeg havde allerede committet den.**
   Jeg skrev at både `createElement("style")` og de 35 `style={{}}` tvang direktivet. Målt
   isoleret: Reacts CSSOM-vej giver **nul** violations under `style-src 'self'` (attributten står
   i DOM'et alligevel — CSP rører ikke CSSOM), mens `react-remove-scroll`s `<style>` +
   `createTextNode` giver én. Rettet i `e377a420`. Direktivet var stadig nødvendigt; **min grund
   var det ikke.**
4. **Første rate-limit-måling var forurenet af mig selv.** 2 igennem i stedet for 6, fordi et
   fejlet zsh-forsøg (`declare -A`) havde afsendt requests *før* det fejlede og drænet bucket'en.
   Ny variant af en kendt fælde: **en fejlet kommando kan have haft bivirkninger inden den
   fejlede.** Frisk zone → præcis 6, som nginx dokumenterer.
5. **Kontrol B beviste ingenting i første forsøg.** Sibling-containeren fik 401 — men hosten
   gjorde også, fordi der var gået 18s og tokens var genopfyldt. En "bestået" kontrol hvor
   treatment-tilstanden ikke var etableret. Strammet: host 429, sibling 401, host straks efter
   stadig 429.

## Og én gang hvor målingen ændrede konfigurationen

Planen foreskrev **én** zone. Med login og register i samme zone drænede 12 register-requests
bucket'en, og login svarede 429 med det samme. Sammen med at `$remote_addr` er Docker-gatewayen
for al host-trafik — altså **én global bucket** — betød det at nogen der hamrer register kunne
spærre alles login. **Bremsen indførte selv en DoS-sti.** To zoner koster én linje; efter
opdelingen: register 429, login 401.

## Hvad der ikke kunne bevises

**C2-kontrollen i sin app-nære form.** At vise at `'unsafe-inline'` er nødvendig *i appen*
kræver at en radix-dialog åbnes, altså et klik. Proben klikker ikke, og der er ingen
browser-automatisering i repoet. Mekanismen blev derfor bevist isoleret — en svagere form, og
det står i `nginx.conf` som sådan.

Det er samtidig det stærkeste argument der er kommet for at anskaffe browser-automatisering:
**dette items ene ægte fund kom fra en browser, og det næste ville kræve et klik.**

## Praktisk, til næste gang

- **Headless Chrome er brugbart som instrument her**, men det hænger på nedlukning efter
  `--dump-dom`. Kør det i baggrunden, `sleep`, `kill -9` — dump'et er skrevet inden. Verificér
  at instrumentet kan se en fejl (jeg brugte `script-src 'none'`), ellers betyder "0 violations"
  ingenting.
- **Nested bind mount i en `:ro`-mountet mappe fejler** (`create mountpoint … read-only file
  system`). Kopiér webroot til scratchpad og mount den i stedet.
- **En throwaway-nginx på compose-netværket med muteret config** er langt hurtigere end at
  genbygge imaget per kontrol, og den rører ikke den kørende container.
- `periodOverview` returnerer **tavse nuller** uden `X-Account-ID` i stedet for en fejl. Det
  kostede tid at attribuere; bekræftet med kontrol (med header: 25.000/1.629,75, uden: 0/0).
  Samme mønster som det allerede kendte "X-Account-ID-fejlen lyver".

## Efterladt i dev-stakken

Verifikationen krævede rigtige data: bruger `csp_probe` (id **368**), konto **371** og **fem**
transaktioner (juli+juni 2026, 1.629,75 i udgifter, 25.000 i indkomst). De er **ikke** ryddet op.
Det er bevidst — de er forudsætningen for at kunne gentage browser-verifikationen — men de tæller
med i ES (`transactions_v2`), så et fremtidigt doc-count ikke matcher tidligere sessioners tal.

## Efterspil: CI hang på analytics (ikke på ændringen)

Pushet af de fem commits gav en kørsel der stod `in_progress` i 14 minutter på
analytics-service. **Det var en transient flake, og genkørslen er beviset:** samme commit, ingen
kodeændring, grøn. Havde årsagen ligget i ændringen, kunne det ikke ske. Pushet rørte i øvrigt
nul analytics- eller shared-filer.

Diagnosen er værd at gemme, fordi den var besværlig af strukturelle grunde og ikke af tekniske:
`collected 123 items` fulgt af 836 s stilhed, mod 36 s til første `PASSED` i den foregående
grønne kørsel — de 36 s *er* `es_container`-fixturen. **Loggen kunne ikke læses mens jobbet
kørte** (`BlobNotFound`), så den måtte aflyses for at kunne undersøges: man giver op først og
diagnosticerer bagefter. Og baselinen fandtes kun fordi tidligere kørsler tilfældigvis lå i
loggen; der er ingen alarm på varighed.

Skrevet ned som **P2-38** +
[finding](../findings/2026-07-28-ci-job-can-hang-undetected.md). Fejlmoden er dagens
gennemgående: noget der ser ud som om det virker — her en kørsel der ser ud som om den arbejder.
