---
title: P2-28 — taksonomi-mutationer internal-only
date: 2026-07-29
status: done
backlog-items: [P2-28]
related:
  - ../decisions/2026-07-29-taxonomy-authorization.md
  - ../findings/2026-07-26-product-surface-sweep.md
  - ../../docs/adr/0005-nginx-as-security-perimeter.md
  - ../decisions/2026-07-28-nginx-as-perimeter.md
  - ../plans/2026-07-27-p115-categorize-auth-and-secret-rotation.md
---

# P2-28 — taksonomi-mutationer internal-only

## Goal

De seks skrive-ruter på den globale taksonomi flytter fra `/api/v1/categories` og
`/api/v1/subcategories` til `/api/v1/internal/…` bag den `require_internal_api_key`-guard
servicen allerede har, så en almindelig bruger-JWT ikke længere kan skrive i data som alle
brugere deler. Læse-ruterne er uændrede. Færdig når: en normal bruger-token der **før**
kunne omdøbe en kategori og få navnet propageret til *en anden brugers* transaktioner i
Elasticsearch, **efter** får 405 gennem perimeteren og 401 direkte mod servicen — og
`GET /api/v1/categories/` svarer det samme med samme token hele vejen igennem.

## Context

P2-28 kom fra [product-surface-sweepet](../findings/2026-07-26-product-surface-sweep.md)
(SEC-5). Undersøgelsen 2026-07-29 flyttede itemet på tre punkter, og de står her frem for i
backlog-rækken fordi de ændrer *hvad* der skal fikses:

1. **`DELETE` er allerede vagtet — sweepets formulering "one user's delete lands in every
   other user's categorizations" holder kun delvist.** `category_service.py:146` afviser en
   kategori der har subkategorier (`CategoryHasSubcategories`), og `:264` afviser en
   subkategori der hedder `"Anden"` (rule-enginens absolutte fallback, jf.
   `FALLBACK_SUBCATEGORY_NAME`), har merchant-mappings eller har regler der peger på den.
   Det der faktisk kan slettes er tomme kategorier og blad-subkategorier uden referencer.

2. **Den uvagtede fan-out er `PUT`, ikke `DELETE`.** `update_category` (`:104`) har nul
   guards, og prisen står i `analytics-service/app/application/projections.py:143`: ved et
   anvendt rename kalder `TaxonomyProjector.handle_category` **`propagate_category_rename`**,
   som omskriver det denormaliserede `category_name` på alle transaktions-docs i ES — på
   tværs af alle brugere. `:158` gør det samme for subkategorier. Ingen "in use"-guard kan
   fange et rename, fordi intet bliver forældreløst. Dertil kan `type` ændres
   expense↔income, hvilket flytter kategorien mellem aggregeringerne for alle.

3. **Det er en shippet feature, ikke kun en manglende dependency.** `CategoriesPage.jsx:59`
   har en "Administrer kategorier"-knap der åbner `CategoryManagement`. Brugeren *tilbydes*
   at redigere den globale taksonomi.

**Valget mellem de fire modeller blev truffet 2026-07-29 og skrives op som decision-doc i
trin 1.** Kort: perimeteren lukker `/api/v1/internal/*` gratis — `nginx.conf:139` er en
deny-backstop (`return 404`) og kommentaren over den registrerer at netop
`/api/v1/internal/accounts/1/exists` blev målt 2026-07-28 — så internal-only kræver **nul**
nginx-ændringer og er den mekanisme ADR-0005 blev bygget til. En `is_admin`-rolle blev
fravalgt fordi der hverken findes en admin-UI eller en måde at *tildele* rollen uden at røre
DB'en; den ville altså give samme praktiske resultat (out-of-band administration) mod en
user-migration og et JWT-claim som alle 12 services ser.

**En påstand jeg selv fremsatte undervejs var forkert og er værd at have skrevet ned:** jeg
rapporterede at categorization-service *ikke* har en `INTERNAL_API_KEY`. Den har
(`config.py:17`), sammen med en færdig fail-closed guard i `categorize_api.py:31-47`
(`compare_digest`, 503 når nøglen er ukonfigureret, 401 ved forkert nøgle) sat **router-level**
med begrundelsen *"a future endpoint added to this router is then guarded by default rather
than by remembering to opt in"*. Min grep ramte et zsh-glob der ikke matchede, hvilket
afbrød hele kommandoen, så den første del aldrig kørte — og jeg læste et tomt output som et
negativt resultat. Samme klasse som [[feedback_pipe_hides_exit_code]]. Konsekvensen for
planen er positiv: guarden skal **genbruges**, ikke skrives.

## Non-goals

- **Læse-stien ændres ikke.** `GET /api/v1/categories/`, `GET /api/v1/categories/{id}`,
  `GET /api/v1/categories/{id}/subcategories` og `GET /api/v1/subcategories/` beholder sti,
  JWT-krav og svar-form. Gateway'ens `categories`/`subcategories`-felter
  (`graphql_api.py:556, :571`) og frontendens `useCategories`/`useSubcategories` er urørte.
- **Ingen rollemodel.** Ingen `is_admin`-kolonne, intet nyt JWT-claim, ingen ændring i
  `services/shared/auth`. Admin-brugeren filed som feature-item i trin 6.
- **Ingen ændring af taksonomiens ejerskab.** ADR-003 står — categorization-service er
  fortsat eneste skriver. Denne plan rører *autorisation over* taksonomien, ikke ejerskab af
  den, og skal ikke skrives ind i ADR-003.
- **Ingen ændring af `/api/v1/rules`.** Regler har en `user_id`-kolonne og er per-bruger
  ejede; de er ikke delt state og hører ikke i dette item.
- **Guardens *form* ændres ikke.** `require_internal_api_key` genbruges som den er, inkl. at
  en ukonfigureret nøgle giver 503 (P1-15's beslutning). Vi indfører ikke en ny variant.
- **Ingen nginx-ændring.** Deny-backstoppen dækker allerede `/api/v1/internal/`, og en
  eksplicit `location` ville kun kunne gøre det værre (P3-44's fælde: en rute på den
  offentlige overflade der ser lukket ud).
- **Domænelogikken i `CategoryService` er urørt.** Ingen guard tilføjes eller fjernes; de
  eksisterende `CategoryHasSubcategories`/`SubCategoryInUse` bliver stående.

## Steps

1. [x] **Decision-doc.** `dev-notes/decisions/2026-07-29-taxonomy-authorization.md` — de fire
   overvejede modeller (internal-only, `is_admin`, per-bruger-taksonomi, kun-`PUT`), hvorfor
   internal-only, og de to målinger der bærer valget: perimeterens deny-backstop, og at
   taksonomien allerede har en ejer-kontrolleret ændringssti i migrationerne
   `002_seed_categories` / `003_seed_subcategories` / `006_heal_display_order_and_emit_taxonomy_seed_events`.
   Eksplicit noteret: valget er **reversibelt** — guarden sidder router-level, så en senere
   `is_admin` er ét linjeskift på routeren, ikke en omskrivning. Ikke ADR-materiale (det er en
   autorisationsbeslutning i én kontekst, ikke en systemgrænse).

2. [x] **Split routerne.** `services/categorization-service/app/adapters/inbound/category_api.py`.
   Diff-formen er tre routere frem for to, hvor de eksisterende handler-kroppe flyttes
   uændret:

   | Rute i dag | Efter | Guard |
   |---|---|---|
   | `GET /api/v1/categories/` | uændret | JWT |
   | `GET /api/v1/categories/{id}` | uændret | JWT |
   | `GET /api/v1/categories/{id}/subcategories` | uændret | JWT |
   | `GET /api/v1/subcategories/` | uændret | JWT |
   | `POST /api/v1/categories/` | `POST /api/v1/internal/categories/` | `X-Internal-API-Key` |
   | `PUT /api/v1/categories/{id}` | `PUT /api/v1/internal/categories/{id}` | `X-Internal-API-Key` |
   | `DELETE /api/v1/categories/{id}` | `DELETE /api/v1/internal/categories/{id}` | `X-Internal-API-Key` |
   | `POST /api/v1/categories/{id}/subcategories` | `POST /api/v1/internal/categories/{id}/subcategories` | `X-Internal-API-Key` |
   | `PUT /api/v1/subcategories/{id}` | `PUT /api/v1/internal/subcategories/{id}` | `X-Internal-API-Key` |
   | `DELETE /api/v1/subcategories/{id}` | `DELETE /api/v1/internal/subcategories/{id}` | `X-Internal-API-Key` |

   Guarden sættes **router-level** på skrive-routeren (`dependencies=[Depends(...)]`), af
   samme grund som `categorize_router` gør det. `require_internal_api_key` flyttes fra
   `categorize_api.py` til et delt sted i samme lag (fx `app/adapters/inbound/internal_auth.py`)
   og importeres begge steder — ikke kopieres; en anden kopi er præcis P2-36's fejlklasse.
   `_user_id: int = Depends(get_current_user_id)` fjernes fra skrive-ruterne: den resolverer
   en identitet ingen bruger, og at lade den stå ville antyde en ejerskabskontrol der ikke
   findes. Registrér den nye router i `main.py:94-97`.
   Opdatér modulets docstring, som i dag beskriver et "Routing layout" der bliver forkert.

3. [x] **Frontend: fjern skrive-overfladen.** Modalen kan ikke blive stående og kalde ruter
   der svarer 405.
   - Slet `components/CategoryManagement/` (`CategoryManagement.jsx` 242,
     `SubcategoryList.jsx` 151, `CategoryManagement.css` 343).
   - `pages/CategoriesPage.jsx`: fjern importen (`:7`), knappen (`:56-62`),
     `showManagementModal`-state, `handleCategoryChange` og `<CategoryManagement>`-blokken
     (`:106`). `Modal`-importen fjernes hvis den bliver ubrugt.
   - `api/categories.jsx`: fjern `createCategory`/`updateCategory`/`deleteCategory`; behold
     `fetchCategories`. Bemærk at `crudFactory` så kun bruges til `fetchAll` her — lad
     factoryen være, den har andre forbrugere.
   - `api/subcategories.jsx`: fjern `createSubcategory`/`updateSubcategory`/
     `deleteSubcategory`; behold de to fetch-funktioner.
   - `useCategories`/`useSubcategories` er **read-only hooks** og bliver stående — de bruges
     af `TransactionForm`, `RulesPage`, `TransactionsPage`.
   - Der findes ingen unit-test af `CategoryManagement`, så sletningen brækker ikke en test.
     Det er også en dækningsgrænse værd at nævne i Outcome, ikke en tryghed.

4. [x] **Tests.** `services/categorization-service/tests/integration/test_category_router_crud.py`
   er det eneste sted i repoet der kalder skrive-ruterne (verificeret repo-bredt). De syv kald
   på `:80,85,90,95,100,114,119` skal pege på de nye stier og sætte `X-Internal-API-Key`.
   Ny test-fil i samme mappe, modelleret efter `test_categorize_router_auth.py` (som er DB-fri
   og monkeypatcher servicen), der asserterer **fire** ting:
   - hver af de seks skrive-ruter uden nøgle → **401**,
   - med forkert nøgle → **401**,
   - med en gyldig **bruger-JWT** og ingen intern nøgle → **401** (den ægte regression: en
     bruger-token må ikke være tilstrækkelig),
   - de fire læse-ruter med bruger-JWT → uændret **200**.
   Sidste punkt er ikke pynt: uden det er "alt er lukket" og "det virker" ikke til at skelne.

5. [x] **Verifikation — se `Verification` nedenfor.** Kør før koden ændres (baseline) og efter.

6. [x] **Docs.** `BACKLOG.md`: P2-28 → `done YYYY-MM-DD` med link hertil, og rækken skal
   forblive én linje (rapporten hører i Outcome). Nyt item i `FEATURES.md`: **admin-bruger
   med cross-tenant analyse-dybde**, hvor det dyre navngives som *cross-tenant læsning* og
   ikke som rollen — `analytics-service/.../query_store.py:13` erklærer tenant-isolation, og
   `user_id: int` er en obligatorisk positional parameter på hver query-metode (`:151, :246,
   :296, :339, :394, :498`), så der findes ingen "alle brugere"-sti at autorisere; den skal
   bygges. *Builds on*: `shared/auth`s `decode_token` returnerer allerede hele claims-dicten,
   så et nyt claim kræver nul JWT-ændringer. *Needs first*: F2-08. Notér også det billigere
   alternativ til formålet "analysere egne sandbox-data": Grafana/Kibana read-only mod ES,
   som kræver nul produktionskode. Andet nyt item: **per-bruger custom-kategorier** —
   `create_subcategory` sætter allerede `is_default=False` med kommentaren om at brugerskabte
   subkategorier skal kunne skelnes fra seeds, så designet havde det i tankerne; den er L
   fordi `categories.name` er globalt unique og hver læse-sti i gateway/analytics/transaction
   rører den. Opdatér `00-INDEX.md` og `STATUS.md`.

## Verification

**Baseline først, mens koden stadig er som den er.** Uden en før-måling er efter-tallet ikke
et bevis for noget. To brugere med transaktioner i ES er en forudsætning — dev-stakken har
allerede `csp_probe` (368) og konti 370/371 stående fra P2-39 trin 8.

1. **Blast radius, før:** som bruger A, `PUT /api/v1/categories/{id}` gennem perimeteren på
   `127.0.0.1:3000` der omdøber en kategori bruger B har transaktioner i. Forvent **200**, og
   verificér derefter i ES at **bruger B's** transaktions-docs har fået det nye
   `category_name` (det er `propagate_category_rename`). Det tal er itemets eksistensberettigelse.
   Døbes tilbage bagefter.
2. **Efter fixet, tre prober:**
   - Samme `PUT` gennem perimeteren → **405**. Bemærk: *ikke* 404 og *ikke* 403.
     `location /api/v1/categories` er en præfiks-proxy, så requesten når stadig servicen —
     den har bare ikke længere en `PUT` på den sti, og FastAPI svarer Method Not Allowed.
     Skriv det ned, ellers ser det ud som en fejl i verifikationen.
   - `PUT /api/v1/internal/categories/{id}` gennem perimeteren → **404** fra deny-backstoppen
     (`nginx.conf:139`), uden at requesten når servicen.
   - Direkte mod `127.0.0.1:8005`: `PUT /api/v1/internal/categories/{id}` uden nøgle → **401**;
     med `X-Internal-API-Key` → **200**, og renamet propagerer igen. Sidste del er kontrollen
     mod at vi har lukket ruten frem for at flytte den.
3. **Kontrol at læsestien lever:** samme bruger-token, `GET /api/v1/categories/` gennem
   perimeteren → **200** med samme antal kategorier som i baselinen.
4. **Browser-suiten:** `make test-browser`. Den seeder én bruger og driver dashboardet;
   den skal være **uændret grøn** — kategorierne læses stadig. Bliver den rød, har vi ramt
   læsestien.
5. **Service-suiten:** `make -C services/categorization-service test` og `… typecheck`
   (servicen er på mypy-gaten, jf. `TYPECHECK_SERVICES`).
6. **Frontend:** `npm test` i `services/frontend` — 346 tests skal være grønne på nær dem der
   måtte referere den slettede komponent (ingen fundet, så forvent 346).
7. **`make compose-check`** — rule 5 læser `nginx.conf` mod compose. Vi ændrer ikke nginx, så
   den skal være grøn; kører for at bevise at antagelsen holdt.
8. **CI grøn**, og aflæst *navngivet* i loggen frem for som "success" — den nye auth-testfil
   skal ses køre.

## Risks & rollback

- **Størst risiko: en forbruger vi ikke fandt.** Repo-bredt grep gav kun servicens egen
  testfil, og gateway rører kun læse-felterne. Men et *menneske* eller et notebook-script kan
  have kaldt ruterne ad hoc. Detektion: 405 i categorization-services access-logs efter
  deploy. Konsekvensen er en fejlet skrivning, ikke datatab.
- **Frontend-sletningen er den eneste irreversible del af diffen.** Den er i git, og
  per-bruger-kategorier (feature-itemet) ville alligevel kræve en anden komponent, fordi
  ejerskabsmodellen er en anden. Rollback = `git revert`.
- **`INTERNAL_API_KEY` ukonfigureret i et miljø** giver 503 på skrive-ruterne frem for 401.
  Det er P1-15's bevidste valg og ikke en regression — men det betyder at et miljø uden
  nøglen ikke kan seede taksonomi via API'et. Seeding sker via migrationer, så det er ikke en
  ny begrænsning; nævnt her så det ikke fejldiagnosticeres som "guarden virker ikke".
- **At flytte `require_internal_api_key` ud af `categorize_api.py`** rører P1-15's kode.
  `test_categorize_router_auth.py` er den eksisterende vagt og skal blive grøn uændret —
  hvis den kræver ændringer, er flytningen ikke ren, og så skal den rulles tilbage til en ren
  import frem for en omskrivning.
- **Rollback samlet:** ét revert af hele serien. Ingen migration, ingen event-kontrakt, intet
  persistent state ændres — det er den egenskab der gør itemet lille.

## Outcome

**Done 2026-07-29.** De seks skrive-ruter ligger under `/api/v1/internal/…` på en tredje
router med `dependencies=[Depends(require_internal_api_key)]`. Guarden blev flyttet til
`app/adapters/inbound/internal_auth.py` og importeres af begge routere.

### Baseline-tallet, som var itemets eksistensberettigelse

Målt mod den kørende stak **før** koden blev ændret. En bruger registreret ét minut i
forvejen (`p228_probe`, id **466**), som ejer **nul** transaktioner, kaldte
`PUT /api/v1/categories/1` gennem perimeteren → **200**. Derefter i ES:

| | Tal |
|---|---|
| Docs med det nye `category_name` | **150** |
| Distinkte brugere ramt | **23** |
| Heraf bruger 466's egne docs | **0** |

At tallet for brugerens *egne* docs er 0 er det der gør fundet skarpt: skrivningen havde
udelukkende effekt på andre. Døbt tilbage; 150 docs restaureret, 0 rester.

### Efter fixet — de fem prober, alle som forudsagt

| Probe | Forventet | Målt |
|---|---|---|
| `PUT /api/v1/categories/1` gennem perimeteren, bruger-JWT | 405 | **405** |
| `PUT /api/v1/internal/categories/1` gennem perimeteren | 404 (deny-backstop) | **404** |
| `PUT /api/v1/internal/categories/1` direkte, uden nøgle | 401 | **401** |
| Samme, med gyldig bruger-JWT og ingen nøgle | 401 | **401** |
| Samme, med `X-Internal-API-Key` | 200 + propagerer | **200**, 150 docs |

Den sidste række er kontrollen mod at have *lukket* ruten frem for at *flytte* den — uden
den er "alt er 401" og "det er i stykker" ikke til at skelne. Læsestien: alle fire GET-ruter
**200** med samme token, og **11 kategorier** som i baselinen.

### Suiter

`make -C services/categorization-service test` **165 passed**, `lint` + `typecheck` (mypy: 41
filer) rene. `npm test` **346 passed** — præcis det planen forudsagde. `make test-browser`
**4 passed** (suiten er vokset fra 2 til 4 siden planen blev skrevet). `make compose-check`
grøn: 20 nginx-locations, 18 upstreams — antagelsen om nul nginx-ændringer holdt.

### Tre ting undersøgelsen rettede undervejs

1. **Planen sagde 7 skrive-kald i `test_category_router_crud.py`; der er 8.** Linje 70's
   `POST` blev ikke talt. Alle 8 er flyttet. En optælling i en plan er også et instrument.
2. **Flytningen af guarden var ren, og af en grund planen ikke havde fanget.**
   `test_categorize_router_auth.py` blev grøn uændret — ikke fordi flytningen var forsigtig,
   men fordi den monkeypatcher `categorize_api.settings`, altså selve *settings-objektet*, og
   begge moduler holder samme reference. Havde testen patchet modul-attributten, ville en ren
   import have brækket den. Risikoafsnittets betingelse var altså opfyldt ved held så meget
   som ved design; værd at vide hvis guarden flyttes igen.
3. **`503`-beskeden ændrede sig fra "Sync categorization is not configured" til "Internal API
   is not configured"**, nu guarden dækker to routere. Ingen test asserterede på strengen.

### Dækningsgrænser, navngivet frem for glattet

- **Der fandtes ingen unit-test af `CategoryManagement`**, så sletningen af 736 linjer
  frontend brækkede ingenting. 346 grønne tests er derfor *ikke* et bevis for at sletningen
  var korrekt — ingen af dem så komponenten. Browser-suiten dækker dashboardet, ikke
  `/categories`-siden.
- **`test_old_public_path_no_longer_writes`** accepterer både 404 og 405, fordi den kører mod
  TestClient hvor nginx ikke er i vejen. Live-proben er den der binder 405 fast.
- **Bruger 466 blev efterladt** i dev-stakken. Den har nul transaktioner og påvirker derfor
  ikke fremtidige ES-doc-counts, i modsætning til `csp_probe`'s fem.

### Hvorfor approachen virker

Fixet flytter **autorisation**, ikke domænelogik: ingen guard blev tilføjet i
`CategoryService`, fordi ingen domæne-guard *kan* fange et rename — der bliver intet
forældreløst, og `propagate_category_rename` er en korrekt konsekvens af en tilladt
handling. Problemet var aldrig at handlingen var ulovlig, men at den forkerte part fik lov.
Derfor hører fixet i adapter-laget.

At det kostede nul nginx-ændringer er ADR-0005's deny-backstop der betaler sig: fordi
perimeteren er en allowlist med `return 404` som bund, er "flyt ruten under
`/api/v1/internal/`" i sig selv en deployment af den. En eksplicit `location`-blok ville have
været et skridt tilbage — P3-44's fælde, en rute på den offentlige overflade der *ser*
lukket ud.

Prisen vi accepterer: taksonomien kan nu kun ændres out-of-band (migration eller intern
nøgle). Det er acceptabelt fordi det er den tilstand systemet reelt var i — seeding sker
allerede i migrationerne — og fordi guarden sidder **router-level**, så en senere `is_admin`
(F2-14) er ét linjeskift frem for en omskrivning. Vi har gjort en utilsigtet overflade
eksplicit, ikke fjernet en kapabilitet nogen brugte.
