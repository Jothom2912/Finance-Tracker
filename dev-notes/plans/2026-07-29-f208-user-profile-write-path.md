---
title: F2-08 — Profil & indstillinger: den første skrive-sti til en eksisterende bruger
date: 2026-07-29
status: done
backlog-items: [F2-08]
related:
  - ../findings/2026-07-26-product-surface-sweep.md
  - ../backlog/FEATURES.md
  - ../../docs/adr/0005-nginx-as-security-perimeter.md
---

# F2-08 — Profil & indstillinger: den første skrive-sti til en eksisterende bruger

## Goal

Brugeren kan skifte sin egen adgangskode og sit eget brugernavn fra en profilside, nået
gennem en brugermenu i navigationen. Færdig når: (a) et password-skift kan drives
end-to-end — nyt password virker ved login, gammelt afvises; (b) et brugernavn-skift er
synligt i navigationen **uden re-login**; (c) et forkert `current_password` giver **403 og
ikke 401**; (d) `make -C services/user-service check` og `test` er grønne, og
`make test-browser` dækker begge flows.

Det egentlige mål er dog ikke de to formularer. Det er at `user-service` for første gang får
en skrive-sti til en eksisterende bruger overhovedet — porten, repository-metoden,
use casen, ruten. F2-09, F2-10 og F2-14 venter alle udelukkende på at den findes.

## Context

[Product-surface sweepets §0](../findings/2026-07-26-product-surface-sweep.md) er
motivationen: *der findes intet user-domæne.* Verificeret igen 2026-07-29 i kilden —
`IUserRepository` (`ports/outbound.py:12-25`) har `create` plus tre `find_by_*` og **ingen
update**; `IUserService` (`ports/inbound.py:8-18`) har præcis tre metoder; `users` har fem
kolonner uændret siden migration 001. Alle andre bounded contexts er extracted og hærdet.
Denne blev aldrig skrevet.

### Korrektion til sweepets design-constraint

Sweepet skriver at en email-ændring kræver en full-state `UserUpdatedEvent`, ellers
fabrikeres en read-model-desync af P3-20-klassen. **Målt 2026-07-29 holder præmissen ikke
for systemet som det ser ud i dag:**

- `user.created` har **én** forbruger — account-service
  (`account_creation_consumer.py:50-51`) — og den læser kun `user_id`; `email` og `username`
  smides væk (`:68-79`).
- Repo-bred søgning efter `email`/`username` som kolonne-definitioner uden for user-service:
  **nul hits**. Der findes ingen lagret kopi.
- `email`- og `username`-claims *mintes* (`app/auth.py:31-32`) men **læses af ingen**:
  `shared/auth/auth/jwt.py:55-69` resolver kun `sub`/`user_id`.

De tre faktiske kopier er derfor: account-services **synkrone HTTP-fetch** af `username`
(`user_adapter.py:29-43` — frisk per konstruktion, ingen desync mulig), frontendens
`localStorage.username`, og de ulæste claims. **Den ægte desync er klienten** — og den
kommer fra login-svaret, ikke fra tokenet (`AuthContext.jsx:41-43`). Den fixes af en
`updateUser` i AuthContext, ikke af et event.

### Trufne valg

1. **Scope: password + brugernavn.** Email-ændring er *ude*, og ikke fordi den er dyr (den
   er nu billig) — men fordi den uden en verifikations-sti er account-takeover-halvdelen af
   password-reset uden sikkerheds-halvdelen. Den hører i **F2-09**, hvor verifikation
   lander.
2. **Ingen `UserUpdatedEvent` nu.** Et event uden læsere er uverificerbar infrastruktur der
   kan rådne stille — samme klasse som døde suppression-annotationer og P3-53's `/ready`
   som kun CI læser. Constraint'en nedskrives i stedet, se trin 9.
3. **Formularer som resten af frontenden:** `useState` + `handleSubmit`-validering, fejl via
   den globale toast. React Hook Form + Zod er **ikke** i brug (nul matches i
   `package.json` og `src/`), så CLAUDE.md's konvention beskriver noget der ikke findes.
   Den korrigeres, se trin 10.

## Non-goals

- **Email-ændring, password-reset, email-verifikation** — F2-09.
- **Sletning og dataeksport** — F2-10 (og P2-41 for `Account`s manglende soft-delete).
- **Token-revocation.** Et password-skift invaliderer **ikke** eksisterende tokens. Der er
  ingen revocation-mekanisme i systemet: 60-minutters tokens, client-side-only logout
  (`AuthContext.jsx:52-57`). Efter et skift forbliver et stjålet token gyldigt indtil `exp`,
  altså op til en time. Det er en **navngivet, accepteret asymmetri** i denne omgang, ikke
  et overset hul — og den er hele pointen med at et password-skift ikke er en fuld
  kompromis-inddæmning i dag. Filed som **P3-55** (trin 9).
- **Rolle/admin-felter** — F2-14. Ingen `role`-kolonne tilføjes her.
- **Rate-limit på de nye ruter.** Overvejet og fravalgt: begge ruter kræver et gyldigt JWT,
  så der er ingen anonym brute-force-flade, og `current_password` kan kun gættes af en der
  allerede *er* autentificeret som brugeren. En ny `limit_req_zone` ville være teater plus
  en vedligeholdelseskant (`nginx.conf:150-156`: længste præfiks vinder og **arver intet**,
  så `proxy_pass` skal gentages — glemmes den, svarer ruten 404 fra SPA-fallbacken).
  *Dette er en revision af min egen første vurdering i sessionen, hvor jeg kaldte ruten
  brute-forcebar uden at kvalificere at angriberen allerede skal være inde.*
- **Ingen nginx-ændring overhovedet.** `location /api/v1/users` (`nginx.conf:170`) proxier
  allerede hele præfikset, så `/me/password` og `/me/username` rammer user-service uden
  edit. Verificeret, ikke antaget.
- Adfærd for `register`, `login`, `GET /me` og den interne `GET /{user_id}` er uændret.

## Steps

### Backend — user-service

1. [x] **Migration 003: `updated_at` på `users`.** `migrations/versions/003_add_users_updated_at.py`,
   `revision="003"`, `down_revision="002"`. Én nullable `TIMESTAMP`-kolonne + samme felt på
   `UserModel` (`app/models.py:12-20`). **Den eneste skema-ændring i planen** — password og
   username har allerede kolonner. Begrundelsen: i det øjeblik en entitet bliver mutérbar,
   er "hvornår blev dette ændret" ubesvarligt uden feltet, og repoets konvention er
   soft-delete + audit-trail frem for tavse mutationer.

2. [x] **Udvid `IUserRepository`** (`app/application/ports/outbound.py:12-25`) med tre
   metoder:
   - `find_credentials_by_id(user_id: int) -> UserWithCredentials | None`
   - `update_password(user_id: int, password_hash: str) -> None`
   - `update_username(user_id: int, username: str) -> User`

   `find_credentials_by_id` er **ikke** valgfri bekvemmelighed: den eksisterende
   `find_by_id` returnerer `User` **uden** credentials (`:38-42`, bevidst — se
   `entities.py:17-23`), så et password-skift kan ikke verificere det nuværende password
   gennem den. Det er derfor dette er en port-ændring i tre lag og ikke "en ny rute".

3. [x] **Implementér dem** i `app/adapters/outbound/postgres_user_repository.py`. Genbrug
   `_to_entity` / `_to_credentials_entity`. `update_*` sætter `updated_at` og `flush()`er;
   commit ejes af UoW'en som i `register`.

4. [x] **DTO'er** (`app/application/dto.py`): `ChangePasswordDTO` (`current_password`,
   `new_password` med samme `PASSWORD_MIN/MAX` som `RegisterDTO`) og `ChangeUsernameDTO`
   (`username` med `USERNAME_MIN/MAX`). Genbrug konstanterne `:7-11` — ikke nye tal.

5. [x] **Ny domain-exception** i `app/domain/exceptions.py`:
   `CurrentPasswordIncorrectException(UserException)`.

   **Dette er planens vigtigste enkeltdetalje.** Det oplagte greb er at genbruge
   `InvalidCredentialsException`, men den mapper til **401**, og `apiClient.jsx:59` kalder
   `handleUnauthorized()` på enhver 401 fra en ikke-auth-rute → `clearAuthStorage()` +
   `window.location.replace('/login')`. Et forkert nuværende password ville altså **logge
   brugeren ud** i stedet for at vise en fejl. Den nye exception mapper til **403**, netop
   så den ikke kan konflateres med login-401'en.

6. [x] **Use cases** i `app/application/service.py` + `IUserService`
   (`ports/inbound.py`): `change_password(user_id, dto) -> None` og
   `change_username(user_id, dto) -> UserResponse`.
   - `change_password`: `find_credentials_by_id` → verificér → hash nyt → `update_password`
     → commit. Både verify og hash gennem `anyio.to_thread.run_sync` som `register`/`login`
     (`:59, :113`) — bcrypt er ~250 ms CPU-bundet og må ikke blokere event-loopet.
   - `change_username`: no-op hvis uændret; ellers `find_by_username` → 409 via
     `UserAlreadyExistsException`; fang `IntegrityError` og oversæt til samme 409 som
     `register` gør (`:67-77`) — check-then-insert har det samme race-vindue her.

7. [x] **Ruter** i `app/adapters/inbound/rest_api.py`:
   `PUT /api/v1/users/me/password` → **204**, `PUT /api/v1/users/me/username` → **200
   UserResponse**. Begge `Depends(get_current_user_id)`. Deklarér dem **før**
   `GET /{user_id}` (`:67`) — metoderne kolliderer ikke, men rækkefølgen `/me` før
   `/{user_id}` er den eksisterende regel i filen og skal ikke brydes ved et uheld.
   Exception-mapping: `CurrentPasswordIncorrectException` → 403,
   `UserAlreadyExistsException` → 409, `UserNotFoundException` → 404.

### Frontend

8. [x] **`src/api/users.jsx`** (ny): `fetchMe()`, `changePassword({current_password,
   new_password})`, `changeUsername({username})` mod `USER_SERVICE_URL`
   (`config/serviceUrls.js:20`). **Ikke** `createCrudApi` — det er ikke en CRUD-ressource.
   `apiClient` har ingen `patch`, så `put` (`apiClient.jsx:73-95`).

9. [x] **`AuthContext`: tilføj `updateUser(partial)`.** Merger ind i `user`-state **og**
   skriver `localStorage.username`. Eksportér på context-value (`:81-89`). Det er fixet på
   den ene ægte desync i systemet: `username` i localStorage kommer fra login-svaret, så
   uden dette viser navigationen det gamle navn indtil re-login.

10. [x] **`src/pages/ProfilePage.jsx`** (ny) + rute `/profile` som sibling i `AppContent`
    (`App.jsx:39`) — inde i det auth-vagtede layout. Viser `email` og `created_at`
    read-only, og to formularer. Mønster kopieret fra `RulesPage.jsx:69-93`: `useState` per
    felt, validering i `handleSubmit`, `showError`/`showSuccess` fra `useNotifications()`,
    `disabled={isSaving}` med label-swap. Password-reglerne spejler
    `RegisterPage.jsx:27-34` (confirm-match + min. 8).

11. [x] **Brugermenu i `Navigation.jsx`.** Erstat den statiske
    `<span className="user-info">Logget ind som: …</span>` (`:37-45`) med en dropdown:
    "Min profil" → `/profile`, og "Log ud". Kopiér click-outside-mønsteret fra
    `NotificationBell.jsx:27-36` (`useRef` + `mousedown`-listener kun mens åben,
    `aria-expanded`, `role="menu"`, `data-testid`). Tilføj **Escape-lukning**, som
    NotificationBell ikke har — retrofit ikke klokken her, det er et selvstændigt lille item.

### Dokumentation

12. [x] **Backlog:** F2-08-rækken i `FEATURES.md` linkes til denne plan. To nye rækker i
    `BACKLOG.md`:
    - **P3-55** — password-skift invaliderer ikke eksisterende tokens; ingen
      revocation-mekanisme findes (60-min tokens, client-side logout). Area: user, shared/auth.
    - **P3-56** — `RegisterPage.jsx:81` sætter `maxLength="20"` på brugernavn mens
      `RegisterDTO` tillader 50 (`dto.py:8`); klienten er strammere end kontrakten uden at
      sige det. ProfilePage bruger 50 (kontrakten), så uoverensstemmelsen bliver synlig.
    - Og i FEATURES.md under F2-09/F2-10: noten at den **første** service der lagrer en
      lokal kopi af `email`/`username` skal tilføje `UserUpdatedEvent` i **samme commit** —
      constraint'en fra sweepets §0, nu med den målte præmis vedhæftet.

13. [x] **Korrigér `CLAUDE.md`s Frontend-sektion.** "React Hook Form + Zod til validering
    (trim-then-validate)" beskriver noget der ikke findes i repoet. Erstat med det faktiske
    mønster (`useState` + validering i `handleSubmit`, fejl til global toast) og nævn at et
    RHF+Zod-skifte er et selvstændigt frontend-bredt item hvis det ønskes. En konvention der
    beskriver kode som ikke findes er værre end ingen konvention — den får en review til at
    efterspørge det forkerte.

### Verifikation

14. [x] **Unit** (`tests/unit/test_user_service.py`): password-skift happy path; forkert
    `current_password` → `CurrentPasswordIncorrectException`; uændret brugernavn = no-op;
    optaget brugernavn → `UserAlreadyExistsException`; `IntegrityError` → samme 409.

15. [x] **Integration** (`tests/integration/test_user_api.py`): `PUT /me/password` → 204,
    derefter login med **nyt** password virker og **gammelt** afvises (det er beviset for at
    hashet faktisk blev skrevet, ikke bare at ruten svarede 204); forkert current password →
    **assertér eksplicit 403 og `!= 401`**, med en kommentar der siger hvorfor — det er den
    regression der ellers tavst logger brugere ud; `PUT /me/username` → 200 og `GET /me`
    reflekterer det; uautentificeret → 401.

16. [x] **Browser** (`services/frontend/e2e/profile-write-path.spec.js`, `make test-browser`):
    **må ikke bruge den delte `session`-fixture.** `e2e/fixtures/session.js` er
    worker-scoped og deler **én bruger** på tværs af hele suiten — bevidst, fordi
    perimeteren rate-limiter register til 10r/m burst=5 (`nginx.conf:53-54`). En spec der
    ændrer den brugers password muterer den delte session og vælter enhver efterfølgende
    spec, sandsynligvis som en fejl der ikke ligner sin årsag. Denne spec registrerer derfor
    sin **egen** bruger; det er én ekstra registrering per kørsel, hvilket der er plads til
    under burst=5, men det skal stå i fixturens kommentar, så den næste der tilføjer en
    engangsbruger ved at budgettet er delt.
    Dækker: brugernavn-skift → navigationen viser det nye navn **uden reload** (det er
    `updateUser`-fixet gjort observerbart), og password-skift → log ud → log ind med nyt.

17. [x] **`make -C services/user-service check`** — user-service er på mypy-gaten
    (`ci.yml:158`), så de nye port-metoder er en hård constraint, ikke dokumentation.
    Derefter `make -C services/user-service test` og `make notes-check`.

18. [x] **Live-drev** mod dev-stakken: skift password i UI'et, log ud, log ind med det nye.
    Et grønt `check` er ikke et løfte om at containeren starter — læs user-service' og
    `user-outbox-worker`s logs, ikke kun API'ets.

## Risks & rollback

| Risiko | Detektion | Modtræk |
|---|---|---|
| 403-vs-401-fælden genindføres senere ved en "oprydning" der genbruger `InvalidCredentialsException` | Integrationstesten i trin 15 asserterer `!= 401` eksplicit | Testen er selve vagten; kommentaren i den forklarer hvorfor den ser mærkelig ud |
| E2E-specen bruger den delte session og vælter suiten | Efterfølgende specs fejler på login, ikke på egen assertion | Trin 16 registrerer egen bruger; kommentar i `session.js` om det delte burst-budget |
| Migration 003 "lykkes" mod ingenting | `alembic upgrade head` exit 0 er ikke bevis — verificér at kolonnen findes (`\d users`) | Konventionens eksplicitte gotcha; tjek DATABASE_URL læses fra env i `migrations/env.py` |
| Brugernavn-race giver 500 i stedet for 409 | Unit-testen på `IntegrityError` | Samme oversættelse som `register` allerede gør |
| Nyt password virker, men gammelt token bruges videre | **Forventet**, ikke en bug — se Non-goals og P3-55 | Ingen; asymmetrien er navngivet |

**Rollback:** commits er per logisk fase (migration / porte+repo / use cases+ruter /
frontend / docs), så hvert lag kan revertes for sig. Migration 003 har `downgrade()`.
Frontenden er additiv bortset fra `Navigation.jsx`s højre-slot, som er én blok.

## Outcome

**Shipped 2026-07-29.** Alle 18 trin gennemført som planlagt; ingen trin faldt bort. Seks
commits, ét per lag (migration / porte+repo / use cases+ruter / backend-tests / frontend /
e2e), så hvert lag kan revertes for sig.

### Det planen fik rigtigt

Den vigtigste enkeltdetalje — `CurrentPasswordIncorrectException` → **403** frem for at
genbruge `InvalidCredentialsException`s 401 — holdt hele vejen, og den er nu vogtet i tre
lag: en unit-test der asserterer `not isinstance(..., InvalidCredentialsException)` (de deler
basisklasse, så en `pytest.raises` på den nye ville bestå for begge), en integrationstest der
asserterer `403` **og** `!= 401`, og et browser-trin der viser at sessionen overlever en
forkert indtastning. Den ekstra `!= 401` ser overflødig ud ved siden af `== 403`; den er der
for at navngive regressionen for den næste der læser den.

Diagnosen af den ægte desync holdt også: der var ingen læsere af `email`/`username` uden for
user-service, så der blev ikke skrevet noget `UserUpdatedEvent`, og `AuthContext.updateUser`
var nok. Constraint'en er nu formuleret som en fremtidig betingelse i FEATURES.md frem for
som nuværende gæld.

### Det planen ikke forudså — og hvad det kostede

**To fejl blev fundet af e2e-specen, ikke af planen. Begge var i instrumentet eller i noget
planen kaldte trivielt.**

1. **`addInitScript` re-seeder localStorage ved HVER navigation.** Trin 16's krav om at
   brugernavnet skulle overleve en reload var derfor umuligt at måle på navigationen: efter
   `page.reload()` skrev fixturen det *oprindelige* navn tilbage, og assertionen målte
   fixturen frem for appen. Persistensen måles nu mod serveren i stedet
   (`profile-username-input` fyldes af `fetchMe()`). Samme klasse som instrument-blindheden i
   P2-39/P2-40 — men her fejlede instrumentet højt, hvilket er det heldige udfald.

2. **`ProfilePage`s optimistiske startværdi lod `fetchMe` overskrive brugerens indtastning.**
   Feltet blev initialiseret fra `user?.username`, så et hurtigt submit sendte det *gamle*
   navn hvis svaret landede imellem. Specen var grøn isoleret og **rød under fuld
   suite-belastning** — altså en ægte race, ikke flakiness. Feltet starter nu tomt, fyldes
   kun af serveren, og er `disabled` indtil profilen er hentet. Det er værd at bemærke at
   planen behandlede formularerne som det trivielle trin ("mønster kopieret fra
   RulesPage"); den ene rigtige bug i frontenden lå der.

**Tre tests blev til én.** Første udkast gav hver assertion sin egen test og dermed sin egen
registrering — hvilket modsagde den burst-budget-note trin 16 selv bad om at skrive.
Sekvensen er samtidig den rigtige måle-rækkefølge: password-skiftet skal være sidst, fordi
det ugyldiggør de credentials de foregående trin bruger.

**Fejl-toasts auto-lukker ikke** (`NotificationContext`: kun `success` får en timer) og
containeren ligger over navigationens højre hjørne, så den opsnappede kliksene på
brugermenuen. Specen lukker den nu eksplicit — og bruger lejligheden til at assertere at
brugeren faktisk *ser* en fejl. "Ikke logget ud" alene ville også være sandt hvis knappen slet
ikke gjorde noget.

**`session-fixture.spec.js` måtte røres.** Dens mount-bevis hang på teksten `Logget ind som:`,
som brugermenuen erstatter. Ankeret er flyttet til `user-menu-trigger`, som bærer det samme:
elementet findes kun hvis React mountede, og navnet i det kommer fra AuthContext.

### Verifikation

- `make -C services/user-service check` grøn (ruff + format + mypy, 24 filer) og `test`: 70
  passed (26 unit på servicen + integration).
- `TestUpdatedAtStamp` har en **NULL-kontrol ved siden af treatmentet**, så en kolonne der
  aldrig røres ikke kan læses som en der virker.
- Migration 003 verificeret mod den kørende Postgres med `\d users` — kolonnen findes, ikke
  bare `alembic upgrade head` exit 0. Loggen viser `Running upgrade 002 -> 003`.
- `npx playwright test`: 5/5 grønne mod det byggede image bag perimeteren. Profil-specen kørt
  3× i træk efter fixet på race'en.
- Frontendens 346 jsdom-tests og `eslint src/` grønne.
- Bemærk: `e2e/` er **ikke** dækket af `make lint` (`npx eslint src/`), så specens stil er
  holdt op mod den eksisterende fixture i hånden.
- **Live-drev mod dev-stakken gennem perimeteren** (127.0.0.1:3000), aflæst navngivet frem for
  som "virkede": `register 201` → `login 200` → forkert current password **`403`** → rigtigt
  skift **`204`** → login med nyt **`200`** og med gammelt **`401`** → brugernavn **`200`**.
  Derefter i DB: `live_1785327405_ny|t`, altså både det nye navn og `updated_at IS NOT NULL`.
  `user-service`s og `user-outbox-worker`s logs læst: ingen errors, ingen tracebacks.

### Observation, ikke undersøgt

`logger.info` fra `app/application/service.py` når **ikke** containerens logs. Access-loggen
viser hver rute og statuskode, men hverken den nye `"Changed password for user %s"` eller den
**eksisterende** `"Registered user %s (outbox event queued)"` dukker op — så det er en
pre-existing gap i logging-konfigurationen (app-loggere er ikke hængt på uvicorns handlers),
ikke noget F2-08 indførte. Konsekvensen er at de nye use cases har nul operationel synlighed
ud over statuskoden. Ikke undersøgt om det gælder de øvrige services; det ville være det
første at måle, ikke at antage.

### Afledte items

- **P3-55** — password-skift invaliderer ikke eksisterende tokens; ingen revocation-mekanisme.
  Navngivet asymmetri, ikke et overset hul: ProfilePage siger det til brugeren i klartekst.
- **P3-56** — `RegisterPage`s `maxLength="20"` mod kontraktens 50. Uoverensstemmelsen blev
  *synlig* her, fordi ProfilePage bruger kontrakten: man kan nu vælge et navn på profilsiden
  man aldrig kunne have registreret sig med.
- **CLAUDE.md's Frontend-sektion korrigeret.** "React Hook Form + Zod" beskrev kode der ikke
  findes (nul hits, målt). Erstattet af det faktiske mønster, med noten at et RHF+Zod-skifte
  er et selvstændigt frontend-bredt item.
