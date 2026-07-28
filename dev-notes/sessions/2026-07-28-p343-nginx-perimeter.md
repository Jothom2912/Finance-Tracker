# Session — 2026-07-28 · P3-43: nginx som perimeter, i drift

**Leveret:** ADR-0005 sat i kode. Fem commits, `4d73b527`..`cd9b94fb`. nginx `proxy_pass`'er
per path til de ti services, frontenden kører på relative URLs, de 11 `CORSMiddleware` er
væk, og `scripts/compose_check.py` har en femte regel der vogter nginx.conf mod drift.
Detaljerne bor i [planens Outcome](../plans/2026-07-28-p343-nginx-perimeter.md); dette er
historien.

## Det gennemgående tema: hvert trin havde en måling der modsagde planen

Fem trin, fem forkerte antagelser — og de var ikke tilfældige. Hver eneste handlede om at
**noget så ud som om det virkede.** Det er samme fejlklasse som rule 5 nu vogter imod, hvilket
er en behagelig, men også lidt ubehagelig, symmetri: reglen blev skrevet af nogen der lige
havde ramt fejlen fire gange.

1. **Trin 1: "ikke eksponeret" så ud som "virker".** `/api/v1/internal/accounts/1/exists` og
   `/api/v1/categorize/` var ikke proxyet — de faldt ned i SPA-fallbacken og svarede
   **200 + index.html**. Planen påstod 404. En glemt proxy-regel ville have set præcis lige
   sådan ud. Deraf deny-backstoppen, som er det modsatte af en catch-all.
2. **Trin 1: den første måling målte det forkerte instrument.** Alle seksten ruter så rigtige
   ud, og nginx' access-log havde **nul** requests. En Vite dev-server på `[::1]:3000` vandt
   `localhost` over Dockers `*:3000`, så proben ramte den vite-proxy jeg selv lige havde
   skrevet. Plausible resultater fra den forkerte komponent.
3. **Trin 2: testene beviste ikke ændringen.** Jeg genindførte
   `fetch(\`http://localhost:8000${url}\`)` som **kontrol** — og alle 344 tests bestod stadig.
   De mocker `fetch` og ignorerer URL'en. Et grønt `npm test` betød ingenting her, og det er
   værd at vide, ikke kun at konstatere.
4. **Trin 3: planens før-måling var forkert.** Den forudsagde preflight-200 på en fremmed
   origin; Starlette svarer **400**. Havde jeg brugt evil-rækken som diskriminator, ville
   400→405 have set ud som et resultat uden at være det. Diskriminatoren var rækken med den
   *tilladte* origin, fordi kun den bar `access-control-allow-origin`.
5. **Trin 4: fire assertions blev syv fejlmoder** — fordi jeg skrev kontrollerne før jeg troede
   reglen var færdig. En upstream uden `ports:` og en `location` med modifier er
   **uafgørlige**, ikke bestående. En regel der springer en assertion rapporterer succes for
   noget den ikke har læst.

## Tre fund der er værd at bære videre

**`proxy_set_header Host $host` brækker FastAPI's trailing-slash-redirect.** `$host` stripper
porten, så `/api/v1/accounts` svarede `Location: http://127.0.0.1/api/v1/accounts/` — port 80,
hvor intet lytter (curl exit 7). Syv af seksten ruter giver 307, og `crudFactory` kalder
accounts/goals uden trailing slash. `$http_host` er rettelsen. Det ville have været en halv
frontend, ikke en enkelt knap.

**`pydantic-settings` kører `extra='forbid'`, men kun for dotenv-filer.** En forældet
`CORS_ORIGINS`-linje i en `.env`-fil dræber nu servicen ved import med `extra_forbidden`;
samme værdi som env-var ignoreres stille. Målt begge veje. Ingen container har en `.env` i sin
CWD, så vi rammes ikke — men det er en fælde for enhver der kopierer et gammelt `example.env`
ind i en service-mappe.

**nginx cacher upstream-IP'er ved config-load.** Efter `docker compose up -d` havde genskabt de
elleve services gav *hele* flowet 502, fordi nginx holdt user-services gamle `.17`. Det er
bagsiden af trin 1's egen rettelse: opslaget ved load er grunden til at `depends_on` er et
krav, og samme egenskab gør en cachet IP forældet uden signal. → P3-45, hvor byttet er skrevet
ned frem for anbefalet: `resolver` + variabel i `proxy_pass` giver dynamisk genopslag, men
slår `nginx -t`'s `host not found in upstream` fra.

## Hvad der ikke kunne bevises

**Chat-SSE'ens pipeline.** `qwen3:8b` bliver OOM-dræbt på maskinens 7,8 GB Docker-hukommelse
(`llama-server ... signal: killed`). Kontrolleret at det ikke er perimeteren: samme request
direkte mod `:8007` fejler identisk. → P3-46.

Transporten *blev* målt, og på det der faktisk binder: 9 chunks spredt over **145s** (buffering
ville give ~0), og strømmen levede **162s**, altså forbi defaultens 60s `proxy_read_timeout`.
Det er to designvalg fra planen bevist ved en request der fejlede — værd at holde fast på, at
en fejlende request stadig kan bære et gyldigt bevis om laget under.

**Browser-gennemgangen blev gjort på HTTP-niveau.** Der er ingen Playwright/Puppeteer i
repoet, så DevTools' network-tab er ubekræftet. Bundle-grep'et (0 hits på `localhost:80XX` mod
11 i det gamle build) og access-loggen fra hvert kald dækker samme påstand fra to sider, men
det er ikke det samme som at have set det.

## Sideordnet

- `services/frontend/build/` er **ikke** committet — den er gitignored. Sweepets påstand faldt,
  og follow-up-itemet bortfaldt.
- `gateway-service`s `make check` er rød på bandit B105 (`app/auth.py:55`). Verificeret med
  `git stash` at den er rød på master også — pre-eksisterende, urørt her.
- Pipe-fælden ramte igen: mine `exit=$?` efter `make ... | tail` var `tail`s exit-kode.
  Fanget denne gang, og gateway-fejlen blev først synlig da jeg aflæste den ordentligt.
