---
title: P2-42b — et probe der kan se en brudt afhængighed (banking), + P3-49 bandit-flag-mismatch
date: 2026-07-29
status: done
backlog-items: [P2-42, P3-49]
related:
  - ../findings/2026-07-28-banking-service-dead-in-ci.md
  - ../plans/2026-07-29-p238-p242-ci-missing-signal.md
  - ../plans/2026-07-28-p240-gateway-explicit-account-resolution.md
---

# P2-42b — et probe der kan se en brudt afhængighed (banking), + P3-49 bandit-flag-mismatch

## Goal

banking-service får et endpoint der **rører** sine afhængigheder frem for at bevise at
processen lever, og CI får en gate der læser det. Færdig-kriteriet er ikke "grøn" men
**verificeret rød ved mutation**: med en ulæselig PEM skal den nye gate fejle *mens*
`/health` bliver ved med at svare 200 og `compose_state_check.py` bliver ved med at være
grøn. De to sidste er den negative kontrol — de er præcis de instrumenter der var blinde
for fejlen, og hvis de også bliver røde har jeg målt noget andet end jeg tror.

P3-49 tages med som separat commit: `make check` skal kunne køres lokalt uden at være rød
på noget der ikke er i vejen.

## Context

`findings/2026-07-28-banking-service-dead-in-ci.md` (lektion 2, som finding'en selv kalder
"den vigtigste enkeltlektion"): banking svarede `/health` 200 gennem hele den kørsel hvor
`GET /api/v1/bank/connections` gav 500, fordi `EnableBankingClient` konstrueres per request
og PEM'en først læses dér. Servicen *kørte*.

P2-42a lukkede halvdelen: fejlen er nu **503 + WARNING** frem for 500. Det gør svaret ærligt,
men ændrer intet ved at intet i platformen kan *opdage* tilstanden — den kræver stadig at
nogen kalder en bank-rute. P2-38's worker-gate fanger en **død** container, en anden klasse;
planen navngiver eksplicit at den ikke ville have fanget banking.

Målt tilstand i dag (survey over alle 12 HTTP-services):

- Alle 12 `/health`-handlere returnerer statisk 200. Ingen rører DB, MQ, ES, Ollama eller
  filsystem.
- Der findes **ingen** `/ready`, `/readyz`, `/healthz` eller `/live` i repoet, og **intet**
  health-helper i `services/shared/*`. Der er altså ikke et mønster at følge — dette bliver
  det første.
- Alle 12 compose-healthchecks rammer samme statiske `/health`
  (`docker-compose.yml:708-710` for banking).
- Alle 11 k8s-manifester sætter `readinessProbe` **og** `livenessProbe` på samme
  `httpGet: /health` — readiness og liveness er i dag umulige at skelne.
- `ci.yml:394` `Wait for system` curler `/health` på 12 porte. Kommentaren på
  linje 397-401 navngiver selv hullet dette item lukker.

## Non-goals

- **Ingen ændring af eksisterende adfærd på nogen rute.** `/health` beholder sin statiske
  200 uændret — den er liveness, og en liveness-probe *skal* ikke fejle på en brudt
  afhængighed (så genstarter kubelet en proces der er sund). At `/health` bliver ved med at
  være grøn er en del af verifikationen, ikke en mangel.
- **Ingen ændring af compose-healthchecks eller k8s-probes.** At flytte
  `readinessProbe.path` til `/ready` er den rigtige næste bevægelse, men den ændrer
  trafik-routing i k8s og hører ikke i et S-item sammen med selve endpointet.
- **Kun banking-service.** Ikke 12 services, ikke et `services/shared/health`-helper.
  Banking er den der har en dokumenteret, målt fejlmode; de 11 andre har en hypotese.
  Endpointet designes så det kan løftes (se trin 1), og generaliseringen bliver et
  opfølgnings-item frem for en antagelse.
- **RabbitMQ tjekkes ikke.** Banking skriver via outbox, så en utilgængelig MQ stopper ikke
  skrivninger — det er hele pointen med mønsteret. Et MQ-tjek i API'ets readiness ville
  rapportere noget nedbrud der ikke findes. Workernes MQ-afhængighed er reel, men de har
  ingen HTTP-overflade, og deres gate er container-tilstand (P2-38).
- **P3-49 hæver ikke barren.** Den fjerner en divergens; den gør ikke Low-fund synlige.

## Design: to niveauer i ét endpoint

Det bærende valg, og det sted planen nemmest kunne blive forkert:

**Enable Banking må ikke kunne gøre banking "not ready".** P2-42a's beslutning er at en
deploy uden brugbar PEM er *unavailable-but-correct* — integrationen er valgfri. Hvis
`/ready` gav 503 på en manglende PEM, ville k8s tage poden ud af service, og en deploy der
slet ikke bruger bank-sync ville aldrig komme op. Det ville modsige gårsdagens beslutning
inden for et døgn.

Derfor:

| Afhængighed | Klasse | Brudt ⇒ HTTP | Brudt ⇒ `status` |
|---|---|---|---|
| Postgres (`SELECT 1`) | påkrævet | 503 | `unavailable` |
| Enable Banking (config + PEM + JWT-signering) | valgfri | **200** | `degraded` |

Body rapporterer altid *hver* afhængighed:

```json
{"status": "ready",
 "dependencies": {"database": {"ok": true},
                  "enable_banking": {"ok": true}}}
```

**CI-gaten er strengere end proben, med vilje.** Proben udtrykker "kan denne pod tage
trafik". Gaten udtrykker "er denne stak fuldt konfigureret" — og i CI *bruges* bank-sync
(P2-39 `chmod 644`'er en genereret PEM netop for det), så en `degraded` Enable Banking er
en fejl der. Gaten kræver derfor `HTTP 200` **og** `status == "ready"`. Den forskel er ikke
et kompromis; det er de to spørgsmåls faktiske forskel.

Ærlig begrænsning at skrive i koden: `_get_banking_client()` er en process-wide singleton,
så tjekket beviser **konstruerbarhed**, ikke at PEM'en stadig ligger på disken. Efter første
succesfulde konstruktion vil et senere `rm` af PEM'en ikke få `/ready` til at rapportere
`degraded`. Det er iboende — PEM'en læses kun én gang uanset — men det betyder at gaten
fanger en *fejlkonfigureret deploy*, ikke en *forsvunden fil under drift*.

## Steps

1. [x] **`GET /ready` på banking-service** — `services/banking-service/app/main.py`
       (ny route ved siden af `/health`, ~40 linjer inkl. kommentar) og eventuelt en lille
       `app/readiness.py` hvis routen bliver bredere end en skærm.
       - `database`: `await session.execute(text("SELECT 1"))` via `get_db`. Præcedens for
         formen: `categorization-service/app/rule_engine_provider.py:71`.
       - `enable_banking`: `_get_banking_client()` i `try/except BankConfigError` —
         konstruktøren læser PEM'en *og* smoke-tester RS256-signering
         (`enable_banking_client.py:79`), så én kald dækker alle tre fejlmoder.
         **Skal fanges eksplicit**: uden `except` ville app-level-handleren fra P2-42a
         returnere 503 for hele `/ready` og få den valgfri afhængighed til at se påkrævet ud.
       - `Response(status_code=...)` er husets eneste præcedens for et ikke-200-svar på en
         health-sti (budget + banking bruger den form allerede).
       - Hold funktionen fri af banking-specifik viden ud over selve tjek-listen, så den kan
         løftes til `shared/` senere uden omskrivning.
   → commit: `feat(banking): P2-42b — /ready rører DB og Enable Banking-konfigurationen`

2. [x] **Unit-tests** — `services/banking-service/tests/test_readiness.py` (ny).
       Fire cases: alt ok → 200 + `ready`; PEM-sti findes ikke → **200** + `degraded` +
       `enable_banking.ok == false`; `app_id` tom → 200 + `degraded`; DB rejser → 503 +
       `unavailable`. Den anden case er den vigtigste — den låser beslutningen om at valgfri
       ≠ 503 fast i en test, så en fremtidig "oprydning" ikke kan gøre den til 503 i tavshed.
       *Forbehold:* bankings tests kører kun i CI, ikke lokalt (P3-39 / memory).
   → commit: `test(banking): P2-42b — readiness-niveauer, inkl. degraded ≠ 503`

3. [x] **CI-gate** — `.github/workflows/ci.yml`, nyt step i `e2e-tests` **efter**
       `Wait for system` og ved siden af `Check no container is dead or restarting`:
       curl `/ready` på 8009, kræv HTTP 200 og `status == "ready"`, og **echo hele bodyen**
       så loggen kan aflæses navngivet frem for som "success" (husets vane fra P2-38).
       Ret samtidig kommentaren på `ci.yml:397-401`: den beskriver hullet som åbent.
   → commit: `ci: P2-42b — gate på bankings afhængigheds-readiness, ikke kun liveness`

4. [x] **Verifikation med kontrol** (detaljer nedenfor).

5. [x] **P3-49** — `-ll -ii` ind i `security`-targettet i `services/gateway-service/makefile:26`,
       `services/banking-service/makefile:58` og `services/account-service/makefile:27`, med
       en kommentar om at flagene skal matche `ci.yml:176`/`:260`.
       Målt: gateway `rc=1` uden flag, `rc=0` med — ét Low/Medium-confidence `B105` på
       `app/auth.py:55` (`token = ""`). banking er `rc=0` begge veje; de to andre rettes
       fordi divergensen, ikke fundet, er defekten.
       **Fravalgt:** `# nosec B105` på linjen. Den ville skjule dette fund og efterlade
       divergensen til det næste. Der findes præcedens for `# nosec` i repoet
       (`gateway-service/app/main.py:35`, `B104`), så fravalget er en vurdering, ikke en
       mangel på mønster. **Retningen er lokal → CI, ikke omvendt**: at fjerne `-ll -ii` fra
       CI ville gøre gateway rød i dag på en `""`-sentinel der ikke er en credential.
   → commit: `build: P3-49 — samme bandit-tærskel lokalt og i CI`

6. [x] **Docs** — backlog-rækker (P2-42 → done, P3-49 → done), `STATUS.md`, `00-INDEX.md`,
       finding'ens P2-42b-note, og planens Outcome.
   → commit: `docs: P2-42b + P3-49 — outcome, backlog, STATUS`

## Verification

Alt kører mod den lokale compose-stak; banking på 8009.

**Treatment — instrumentet skal være rødt på den rigtige fejl.** Sæt
`ENABLE_BANKING_KEY_PATH` til en ikke-eksisterende sti, genstart banking-service, og aflæs
alle fire:

| Instrument | Forventet | Hvad det viser |
|---|---|---|
| `GET /ready` | 200 + `status: degraded` | det nye signal virker |
| `GET /health` | **200** | negativ kontrol: den gamle probe *er* blind |
| `compose_state_check.py` | **grøn** | negativ kontrol: P2-38's gate dækker en anden klasse |
| CI-gatens shell-udtryk | **rød** | gaten læser signalet, ikke bare porten |

Bliver `/health` eller worker-gaten røde her, har jeg brudt containeren frem for
afhængigheden, og målingen er ugyldig — genopstil.

**Kontrol 1 — gyldig PEM.** Samme fire: `/ready` 200 + `ready`, gate grøn. Uden denne er
"rød" ikke bevist at komme fra PEM'en (P2-39/P2-40's lektie: en gate der altid er rød er
lige så ubrugelig som en der altid er grøn).

**Kontrol 2 — påkrævet afhængighed.** Peg `DATABASE_URL` på en død host og bekræft `/ready`
= **503**, ikke 200+`degraded`. Aflæs samtidig om containeren i det tilfælde allerede står
`restarting` for P2-38's gate — gør den det, er DB-niveauet **redundant dækning frem for ny
dækning**, og det skal stå i Outcome frem for at blive talt med.

**Kontrol 3 — den ægte fejlmode fra finding'en.** Med brudt PEM: `GET
/api/v1/bank/connections` giver 503 (P2-42a) *og* `/ready` rapporterer `degraded`. Det
knytter det nye signal til den rute der faktisk fejlede, frem for til en hypotese.

Derefter: `make -C services/banking-service test` (kun i CI, jf. P3-39),
`make -C services/gateway-service check` skal være **grøn lokalt** efter trin 5, og en fuld
CI-kørsel aflæst *navngivet* — `/ready`-bodyen i loggen, og de 19 jobs.

## Risks & rollback

- **`/ready` bliver læst som liveness af noget.** Intet peger på den ved merge (non-goal:
  compose og k8s røres ikke), så risikoen er fremtidig. Modvirkes af kommentaren i routen og
  af testen i trin 2 der låser `degraded ≠ 503`.
- **Konstruktion i en readiness-handler har en bivirkning:** det første `/ready`-kald varmer
  singletonen og dens `httpx.AsyncClient`. Det er ikke et nyt objekt-livsforløb —
  `aclose_banking_client()` i lifespan rydder allerede op — men det flytter konstruktionen
  fra første brugerrequest til første probe. Det er en forbedring (fejl-tidligt), og den skal
  navngives frem for at være tilfældig.
- **Gaten kan blive flaky** hvis `/ready` kaldes før DB er klar. Den ligger efter
  `Wait for system`, og banking har `depends_on: postgres-banking: service_healthy`, så
  vinduet er lukket to gange. Hvis den alligevel flakker: det er data om opstart, ikke om
  gaten — undersøg frem for at tilføje et retry.
- **P3-49 kan gøre en fremtidig Medium usynlig lokalt.** Nej — `-ll` er netop Medium-og-op.
  Den skjuler Low, og det er samme sæt CI har håndhævet hele tiden.
- **Rollback:** trin 1-3 er tre uafhængige commits; revert af CI-commiten alene fjerner
  gaten og efterlader endpointet, hvilket er en gyldig mellemtilstand. Trin 5 er tre linjer.

## Outcome

Done 2026-07-29, fem commits (`ee8602aa`, `67c4cddc`, `cf434d37`, `163554fd`, + docs).
Alle tre instrumenter aflæst navngivet mod den lokale stak; ingen af de fire trin gav det
resultat planen gættede på uden forbehold, og to af dem ændrede en konklusion.

### Verifikationen — de fire aflæsninger

Treatment (`ENABLE_BANKING_KEY_PATH` → ikke-eksisterende sti, compose-override):

| Instrument | Forventet | Målt |
|---|---|---|
| `GET /ready` | 200 + `degraded` | ✅ 200, `enable_banking.ok=false`, `"PEM key not found at …"` |
| `GET /health` | 200 (blind) | ✅ 200 |
| `compose_state_check.py` | grøn (blind) | ✅ grøn, 53 containere |
| CI-gatens shell-udtryk | rød | ✅ `rc=1`, `::error::… er 'degraded', ikke 'ready'` |

Kontrol 1 (gyldig PEM): `/ready` 200 + `ready`, gate `rc=0`. Kontrol 3 (den ægte fejlmode):
`GET /api/v1/bank/connections?account_id=1` → **503** med P2-42a's danske detail, `/ready`
→ `degraded`, og begge i loggen i samme sekund. Det nye signal er knyttet til den rute der
faktisk fejlede.

### Fund 1 — DB-niveauets 503 er ikke nåelig ved opstart, og det er ikke bare "redundant"

Kontrol 2 gav et skarpere svar end planen bad om. Med `DATABASE_URL` mod en død host står
containeren **`restarting`** frem for at svare 503: bankings CMD er
`alembic upgrade head && exec uvicorn …` (`Dockerfile:38`), så en DB-fejlkonfigureret deploy
kommer aldrig til at serve HTTP. `/ready` svarede slet ikke; gaten blev rød på *porten*, ikke
på 503-grenen. P2-38's gate blev rød samtidig.

Så DB-niveauet er **redundant for boot-tilfældet** — men ikke dødt kode. Testet separat ved
at stoppe `postgres-banking` *efter* at banking var oppe, altså DB-tab midt i drift
(failover, OOM'et Postgres):

| Instrument | Målt ved DB-tab midt i drift |
|---|---|
| `GET /ready` | **503 + `unavailable`**, `InterfaceError … connection is closed` |
| `GET /health` | 200 — blind |
| `compose_state_check.py` | **grøn** — blind |

Det er den eneste af de tre aflæsninger der ser tilstanden. Præcis formulering til
backloggen: DB-niveauet er redundant ved *deploy*, unikt ved *drift*.

### Fund 2 — `compose_state_check.py` læser en stoppet datastore som forventet

Bivirkning af ovenstående: da `postgres-banking` var stoppet, rapporterede gaten den under
`Exited cleanly (expected)`. Årsagen er `scripts/compose_state_check.py:126` — *enhver*
container med `state == "exited"` og exit 0 er "expected", fordi `ollama-pull` legitimt er
det. `docker compose stop` giver exit 0, så en bevidst stoppet datastore ser identisk ud.
Ikke et hul i CI (intet stopper containere der), og ikke rettet her — men det er en
antagelse gaten gør uden at vide det, og den hører i backloggen frem for i en kommentar.

### Fund 3 — `# noqa: BLE001` var samme fejl som det fravalg vi lige havde begrundet

Første udkast af `_check_database` havde `except Exception as exc:  # noqa: BLE001`.
`ruff.toml` selecter kun `E,F,W,I`, så `BLE` er ikke slået til: noqa'en undertrykte intet og
kunne aldrig blive rød når den blev forkert (`RUF100` er heller ikke slået til). Fjernet.
Det er den præcis samme egenskab som gjorde `# nosec B105` det forkerte valg i trin 5 —
skrevet en time før, i samme plan.

### P3-49 — reglen, og hvorfor den ene nosec i repoet er rigtig

`-ll -ii` ind i alle tre `security`-targets, som kommentar **over** targettet (i recipe'en
ville make echoe den). Målt bagefter: gateway `rc=0`, banking `rc=0`, `make -C
services/gateway-service check` grøn lokalt for første gang.

Planens begrundelse for at fravælge `# nosec B105` holdt ikke — med `-ll` filtreres B105
(Low) alligevel, så nosec'en ville ikke have skjult noget der ellers var synligt. Den ægte
grund er stærkere: **nosec løser ikke mismatchet.** Selv med nosec på `auth.py:55` ville
lokal bandit stadig køre uden flagene, så det næste Low-fund hvor som helst i tre services
divergerede igen. Flagene fixer klassen; nosec fixer en instans, og bliver derefter død
annotation.

Reglen der kom ud af det, verificeret frem for formodet: **nosec er forbeholdt fund der
overlever CI-tærsklen.** Målt ved at fjerne den eksisterende nosec:

```
B104 gateway app/main.py:35  Medium/Medium → rapporteres OGSÅ med -ll -ii  → nosec er load-bearing
B105 gateway app/auth.py:55  Low/Medium    → filtreres af -ll             → nosec ville være død
```

(Bandit warner `nosec encountered (B104), but no failed test on file app/main.py:34` — det er
attribuering til statement-starten frem for til strengen på linje 35. Suppressionen tælles
stadig: `disabled: 1`.)

### Hvad der bevidst ikke blev gjort

`/ready` er ikke koblet på compose-healthchecken eller k8s' `readinessProbe`. At flytte
`readinessProbe.path` er første gang readiness og liveness divergerer i repoet — alle 11
manifester peger begge på `/health` i dag — og det ændrer trafik-routing, hvilket kræver sin
egen verifikation (kommer poden tilbage når DB'en gør?). Men så længe kun CI læser `/ready`
er det funktionelt et test-fixture, og fixtures rådner: opfølgnings-itemet **P3-53** er
oprettet i samme commit som dette lukker, ikke henvist til "senere".

### Note til eksamen

Tre gates, tre klasser af opstartsfejl, og de er ikke ordnet efter strenghed men efter
*hvad de kan se*: `Wait for system` ser en død proces, `compose_state_check.py` ser en
container der ikke kan blive ved med at køre, `/ready` ser en levende proces med en ubrugelig
afhængighed. Det interessante er at den tredje kun kunne bygges rigtigt ved at spørge hvilke
afhængigheder der er *valgfrie* — svaret gjorde proben mildere end gaten der læser den, og
den forskel er de to spørgsmåls faktiske forskel ("kan denne pod tage trafik" vs. "er denne
stak fuldt konfigureret"), ikke et kompromis.
