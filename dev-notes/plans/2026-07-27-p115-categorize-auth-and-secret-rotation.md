---
title: "P1-15 + P2-26: lås /api/v1/categorize, rotér den delte HS256-nøgle, slå require_exp til"
date: 2026-07-27
status: in-progress     # open | in-progress | done | superseded
backlog-items: [P1-15, P2-26]
related:
  - findings/2026-07-26-categorize-endpoint-unauthenticated.md
  - findings/2026-07-26-product-surface-sweep.md
  - backlog/BACKLOG.md
---

# P1-15 + P2-26: lås /api/v1/categorize, rotér den delte HS256-nøgle, slå require_exp til

## Goal

Tre ting der hver for sig er latente og tilsammen er en åben dør:

1. `POST /api/v1/categorize/` har ingen auth og tager `user_id` fra request-body'en, så
   svarets `tier`-felt er et orakel over andre brugeres private F1-02-regler. Demonstreret
   live uden credentials 2026-07-26.
2. Den delte HS256-nøgle står i klartekst i `k8s/secrets.yaml`, som er trackt i et
   **offentligt** repo, og som inline literal 29 steder i `docker-compose.yml`.
3. `require_exp` er bygget men slået fra, så et JWT uden `exp` verificerer og udløber aldrig.

Færdig når: endpointet svarer 401 uden nøgle og 200 med; den gamle nøglestreng findes
ingen steder i trackede filer på nær dev-notes' historiske omtaler; et token uden `exp`
afvises af alle 12 services; og transaktions-oprettelse stadig får sin kategori.

**Hvorfor de tre hører sammen:** hver for sig er (2) og (3) "burde rettes". Sammen er de
forskellen på at en offentliggjort nøgle giver 60-minutters adgang og at den giver
permanent adgang til alle 12 services. Og (1) er den ene af de tre der er *bevist
udnyttelig i dag*, så den styrer rækkefølgen.

## Context

Fra [product-surface sweep](../findings/2026-07-26-product-surface-sweep.md) (SEC-1, SEC-2)
og [findings/2026-07-26-categorize-endpoint-unauthenticated.md](../findings/2026-07-26-categorize-endpoint-unauthenticated.md).
Bygget på en grøn CI-baseline (P2-30 lukket 2026-07-27, run `30258458348`, 18/18 success)
så en regression er synlig frem for at gå i støj.

### Tre påstande i backlog-rækken der ikke holdt ved kildeverifikation

Rettes i BACKLOG.md som del af dette arbejde — ikke slettet, korrigeret:

1. **"transaction-service … already has S2S config" er forkert.** Hverken
   `transaction-service/app/config.py` (9 felter, intet `INTERNAL_API_KEY`) eller
   `categorization-service/app/config.py` (7 felter, samme) har nøglen. Repo-bredt grep
   for `INTERNAL_API_KEY|X-Internal` i categorization-service: **0 hits**. Nøglen skal
   tilføjes på begge sider — det er ikke bare en `dependencies=`-parameter.
2. **P2-26's "one line per `app/auth.py`" holder for 11 af 12.** analytics-service bruger
   slet ikke shared-pakken: `analytics-service/app/auth.py:34` er hånd-rullet
   `jwt.decode(...)` uden `options`, med lowercase settings (`jwt_secret`). Og
   gateway-service har **to** decode-stier (`app/auth.py:31` og `:42`) og henter sin nøgle
   fra `SECRET_KEY`, ikke `JWT_SECRET` (`docker-compose.yml:832`) — den er nem at misse.
3. **Rækken nævner ikke at rotationen rammer 39 steder.** `docker-compose.yml` har ingen
   YAML-anchor og ingen `env_file` for hemmeligheder: `JWT_SECRET` er inline literal 29
   gange, `INTERNAL_API_KEY` 9 gange, plus gateways `SECRET_KEY`. Tre e2e-testfiler
   hardkoder desuden værdien.

### Fundet undervejs: `user_id` i request-body'en er død kode for legitime kaldere

`transaction-service/app/adapters/outbound/categorization_client.py:46,81` sender kun
`{description, amount}` — aldrig `user_id`. Den per-bruger rule-layering sker på den
**asynkrone** sti (`categorization-service/app/workers/transaction_consumer.py:114-116`),
som henter `user_id` fra eventet og aldrig går gennem HTTP. transaction-service er den
eneste kalder i hele repoet (frontend og gateway rører kun `/categories` og
`/subcategories`).

Feltet som udgør oraklet bruges altså udelukkende af en angriber. Derfor fjernes det frem
for kun at blive hegnet ind — se [decision](../decisions/2026-07-27-categorize-internal-only.md).

### Enable Banking: PEM og app-id roteres bevidst IKKE

Brugerbeslutning 2026-07-27: EB-credentialet er **sandbox**, det er i brug, og det skal
blive ved at virke. At det har ligget i git-historik er accepteret. Det er en bevidst
undtagelse fra P1-08-notens "rotate anything credential-shaped regardless" — den regel
sigter på produktions-credentials.

Verificeret ved kildelæsning at opsætningen **allerede** er den rigtige, så ingen bør
"rette" den igen:

- **PEM-filerne er ikke trackede** og er dækket af `.gitignore:12` (`*.pem`). P1-08 gjorde
  sit arbejde her.
- **Compose** mounter PEM'en fra `${ENABLE_BANKING_ACTIVE_PEM_PATH:-./enablebanking-sandbox.pem}`
  (`docker-compose.yml:15`), og app-id'et er en *interpolations-default*, ikke en hardkodet
  hemmelighed: `${ENABLE_BANKING_ACTIVE_APP_ID:-4fc48bf2-…}` (:7). Kommentaren ovenfor
  (:1-5) beskriver designet: sandbox committet så stakken kører ud af boksen, produktion
  kun i utracket `.env`.
- **k8s** monterer PEM'en fra en `enablebanking-pem` Secret der skabes out-of-band af
  `scripts/k8s-up.sh:37-38` (`kubectl create secret generic` fra den gitignorerede fil) —
  den findes med vilje ikke i noget manifest.

**Konsekvens for P2-15:** rækkens klausul "remove real EB app id from tracked files" er
misvisende. Det trackede id er sandbox-id'et og er der med vilje; *produktions*-id'et ligger
allerede kun i utracket `.env`. Rettes i BACKLOG.md sammen med de øvrige korrektioner.

Ude af scope her, men bemærket: `k8s/secrets.yaml` indeholder også ni DB-passwords, og
compose publicerer alle Postgres-instanser på `0.0.0.0` (P3-24), så de er LAN-nåbare med
kendte passwords. Det hører under P3-24/P2-15, ikke denne plan.

### Ærlig afgrænsning af hvad rotation kan

Rotation gør **ikke** den gamle værdi u-disclosed. Den har ligget i et offentligt repos
historik så længe den har været committet, og et force-push evicter ikke hvad GitHub eller
klonere allerede har hentet. Denne plan skifter værdien og sørger for at den nye ikke
committes. Historik-omskrivningen er stadig P1-08's uafklarede brugerbeslutning og røres
ikke her.

## Non-goals

- **Kategoriserings-adfærd ændres ikke.** Den sync-sti bruger i dag kun globale regler
  (fordi klienten aldrig har sendt `user_id`); det gør den også efter. Per-bruger-regler
  bliver ved at virke på consumer-stien, som er uberørt.
- **Ingen ændring af hvordan tokens mintes.** `require_exp` er verifikations-side.
  Budget-services forfalskede brugertokens er stadig P3-02.
- **P2-15 (SOPS/secretGenerator) løses ikke.** Kun det minimum der stopper blødningen:
  `k8s/secrets.yaml` untrackes og erstattes af en template. P2-15 forbliver åben som det
  infra-item den er.
- **P2-28** (enhver bruger kan slette den globale taksonomi) er en anden endpoint-familie
  i samme service og kræver en rolle-beslutning — ikke her.
- **P2-27** (rate limiting) rører ikke denne plan; den afventer P3-24's perimeter-ADR.
- **P1-08's historik-omskrivning** afventer stadig beslutning.
- **Enable Bankings PEM og app-id roteres ikke** og opsætningen ændres ikke — den er
  allerede korrekt. Se afsnittet ovenfor.

## Steps

Rækkefølgen er ikke kosmetisk. To steder er den bærende:

- **Afsender før håndhæver** (A1 før A2): hvis categorization-service kræver nøglen før
  transaction-service sender den, degraderer klienten "graciøst" (`return None`,
  `categorization_client.py:60-71`) og transaktioner holder op med at få kategori på
  sync-stien — tavst. Omvendt rækkefølge er harmløs. Samme form som P1-14's
  tolerante-læser-først.
- **Rotation er atomisk pr. stak** (B1 i én `compose up -d`): JWT_SECRET deles af alle 12
  services, så en delvis udrulning betyder at service A minter tokens service B ikke kan
  verificere.

### Fase A — luk endpointet (den kritiske del)

1. [x] **A1: transaction-service sender nøglen.** `app/config.py` får
   `INTERNAL_API_KEY: str | None = None`; `categorization_client.py` læser den i `__init__`
   og sætter `headers={"X-Internal-API-Key": ...}` på begge `client.post` (:46, :81).
   Mønster fra `goal-service/app/adapters/outbound/account_adapter.py:10-16,28`.
   `docker-compose.yml` transaction-service-blokken (:277-299) og de tre
   transaction-workers der konstruerer klienten får `INTERNAL_API_KEY`.
   *Harmløs alene* — categorization-service ignorerer stadig headeren.
2. [x] **A2: categorization-service kræver nøglen.** Ny `require_internal_api_key` kopieret
   fra `user-service/app/adapters/inbound/rest_api.py:16-28` — `compare_digest`, 503 når
   ukonfigureret, 401 ved mismatch. **Ikke** account-services `!=`-variant (:17-24).
   `config.py` får `INTERNAL_API_KEY: str | None = None` (fail-closed, ikke dev-streng-default).
   Dependency på `categorize_router` (`categorize_api.py:22`), ikke pr. endpoint.
3. [x] **A3: fjern `user_id` fra `CategorizeRequestDTO`** (`app/application/dto.py:8-14`) og
   forenkl `categorize_batch`'s user-udledning (`categorize_api.py:38-46` falder væk).
   `build_categorization_service(user_id=None)` overalt på HTTP-stien. Bind batch med
   `max_items` (foreslået 500, samme loft som `BulkCreateTransactionDTO`).
4. [x] **A4: live-bevis.** Gentag findings' egen demonstration: `curl` mod
   `localhost:8005/api/v1/categorize/` med `"SHOP N PLAY"` og `user_id: 1` uden credentials
   → skal være **401** (var 200 med `tier:"rule", subcategory_id:5`). Med korrekt header →
   200. Og: opret en transaktion via API og bekræft at den stadig får `category_name` — sync-stien
   må ikke være blevet stum.

### Fase B — rotér nøglen ud af trackede filer

5. [ ] **B1: compose til interpolation.** Erstat de 29 `JWT_SECRET`-literals, gateways
   `SECRET_KEY` (:832) og de 9+2 `INTERNAL_API_KEY` med `${JWT_SECRET:?JWT_SECRET mangler}`
   osv. `:?` frem for `:-` med vilje: en tavs fallback til dev-strengen ville gøre hele
   øvelsen dekorativ. Nye værdier i lokal `.env` (allerede gitignored via `**/.env`) og
   placeholders i `example.env`. **Overvej en YAML-anchor** så næste tilføjede service ikke
   genindfører en literal. `x-enable-banking-env`-anchoren (:6-13) røres **ikke** — den er
   allerede interpolation med bevidst sandbox-default.
6. [ ] **B2: tests og Makefile læser miljøet.** `tests/e2e/{test_budget_month_closed,
   test_budget_threshold_alert,test_full_flow}_e2e.py` hardkoder i dag nøglen; de skal læse
   `os.environ` og fejle med en brugbar besked hvis den mangler. Makefile-målet `test-e2e`
   loader `.env` (`set -a; . ./.env; set +a`) så lokal kørsel er uændret i praksis.
   CI's e2e-job sætter allerede `JWT_SECRET`/`INTERNAL_API_KEY` som job-env, og compose
   interpolerer fra shell-miljøet, så CI får dem gratis — **men bemærk at det afslører en
   latent uoverensstemmelse**: jobbet sætter `test-secret` mens testfilerne hardkoder
   `dev-secret-…`, og i dag "virker" det kun fordi compose hardkoder samme literal som
   testene. Efter B1/B2 skal de to stemme, ellers fejler e2e.
7. [ ] **B3: untrack k8s-hemmeligheder.** `git rm --cached k8s/secrets.yaml`, tilføj til
   `.gitignore`, commit `k8s/secrets.yaml.example`. Kun `JWT_SECRET`, `SECRET_KEY` og
   `INTERNAL_API_KEY` bliver placeholders i templaten.
   **`ENABLE_BANKING_APP_ID` beholder sin nuværende værdi som fungerende default** — se
   afsnittet om Enable Banking nedenfor. Tjek om `k8s/kustomization.yaml` refererer filen; i
   så fald fejler `kubectl apply -k` på et frisk clone indtil man kopierer templaten —
   ønsket fail-closed for nøglerne, men det er præcis derfor app-id'et ikke skal
   placeholder'es. `KUBERNETES_GUIDE.md:85` siger i dag `kubectl apply -f k8s/secrets.yaml`
   og skal opdateres til templaten + henvisning til `scripts/k8s-up.sh`.

### Fase C — håndhæv exp

8. [ ] **C1: `require_exp=True` på de 11 shared-kaldsteder.** account (`auth.py:48-51`), ai
   (:17-20), banking (:17-20), budget (:31-34), categorization (:16-19), goal (:13-16),
   notification (:13-16), saga (:17-20), transaction (:14-17), user (:41-44) og gateway —
   sidstnævnte **to** steder (`:31` og `decode_token` i `:42`).
9. [ ] **C2: analytics-service.** `app/auth.py:34` er hånd-rullet; tilføj
   `options={"require_exp": True}` eller migrér til `make_current_user_dependency`.
   Migrering er pænere men er en større diff i den ene service der ikke er på shared-pakken
   — vælg ved kodning, noter valget.
10. [ ] **C3: bekræft at intet minter uden `exp`** før C1/C2 slås til. Kendte mintere sætter
    det (user `:27,33`, account `:35,42`, budget `:25`, analytics `:21`), men grep bredt
    efter `jwt.encode` og verificér — en glemt minter bliver til 401 i produktion.

### Fase D — fail-closed på de tre dev-streng-defaults

11. [ ] **D1:** `goal/config.py:13`, `banking/config.py:17`, `notification/config.py:11`
    defaulter til `dev-internal-api-key-change-in-production`. Skift til `None` + fail fast
    ved startup, som user-service gør. **Risiko:** en container der ikke får variablen
    crash-looper nu i stedet for at køre med en kendt nøgle — det er meningen, men
    verifikationen skal omfatte at *alle* workers stadig starter, ikke kun API'erne.

### Verifikation

12. [ ] Per-service unit/integration: `make -C services/categorization-service test`,
    `make -C services/transaction-service test`, og de øvrige berørte services.
    categorization-services egne tests kalder service-objektet direkte, ikke routeren, så
    A2 brækker ingen eksisterende test — det betyder også at der **skal skrives en ny test**
    for 401/200 på routeren, ellers er dependencyen utestet.
13. [ ] `make test-e2e` — hele suiten, 24/24. Forventet at fange B1/B2-uoverensstemmelser.
14. [ ] Live: A4's to curl-prober, plus et token uden `exp` mod hver af de 12 services → 401.
15. [ ] `grep -rn "dev-secret-key-change-in-production"` over trackede filer → kun
    dev-notes' historiske omtaler tilbage. Samme for `dev-internal-api-key-…`.
16. [ ] `make ci-status` grøn efter push, og bekræft at e2e-jobbet **kørte** (ikke skipped).
17. [ ] Ret de forkerte påstande i BACKLOG.md: P1-15's "already has S2S config", P2-26's
    "one line per `app/auth.py`" (analytics er ikke på shared-pakken), og P2-15's "remove
    real EB app id from tracked files" (det trackede id er sandbox og bevidst).
18. [ ] Bekræft at bank-sync stadig virker efter rotationen — EB-stien deler `INTERNAL_API_KEY`
    med banking-service (D1), så en fejl her rammer den fulde ADR-0003-kæde, ikke kun auth.

## Risks & rollback

| Risiko | Detektion | Modtræk |
|---|---|---|
| A2 før A1 → sync-kategorisering går tavst i stå (klienten sluger fejlen) | A4's transaktions-probe; `docker logs categorization-service` for 401'er | Rækkefølgen A1→A2 er netop modtrækket; revert A2 alene |
| Delvis rotation → service A minter tokens service B afviser | Alle services 401'er på gyldige tokens; e2e falder på første auth | Én `compose up -d` for hele stakken; revert B1-commit og recreate |
| `${VAR:?}` uden `.env` → compose nægter at starte | Øjeblikkelig og højlydt ved `compose up` | Ønsket adfærd; `example.env` + README-note er fixet, ikke en fallback |
| D1 crash-looper en worker der mangler variablen | `docker compose ps` viser restarting; ikke synligt i API-healthchecks | Tilføj variablen til den blok; **verificér alle 57 containere, ikke kun de healthy-markerede** |
| C1/C2 401'er alt hvis en minter mangler `exp` | C3's grep før udrulning; ellers total auth-udfald | C3 er gaten; revert C1/C2 er én-linjers |
| Rotation invaliderer alle udestående browser-tokens | Brugere ser 401 → `handleUnauthorized` hard-reloader til /login (P3-32a) | Accepteret i dev: log ind igen |

Rollback generelt: hver fase er sin egen commit, så `git revert` pr. fase virker. B3 er den
eneste der ikke er rent revertbar — filen forbliver untrackt, hvilket er det ønskede.

## Outcome (fill in when done)

<!-- udfyldes ved close-out -->
