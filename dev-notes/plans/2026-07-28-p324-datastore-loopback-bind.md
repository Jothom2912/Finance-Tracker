---
title: P3-24 (billig halvdel) — datastores skal ikke være LAN-nåelige
date: 2026-07-28
status: done
backlog: [P3-24]
related:
  - ../findings/2026-07-26-product-surface-sweep.md
---

# P3-24 (billig halvdel) — datastores skal ikke være LAN-nåelige

## Goal

De 13 datastore-containere (9 Postgres, RabbitMQ + management, Elasticsearch, Redis, Ollama)
publicerer i dag på `0.0.0.0` og er derfor nåelige fra hele LAN'et. Efter denne ændring lytter
de kun på loopback. Det er gjort når `nc -z <LAN-IP> <port>` fejler for alle 14 port-mappings,
`nc -z 127.0.0.1 <port>` stadig lykkes, og hele host-side-værktøjskæden (e2e, scripts,
ai-eval, alembic) kører uændret.

Perimeter-ADR'en — hvorvidt gatewayen *skal* være perimeter — er ikke i denne plan. Se
Non-goals.

## Context

[Sweepets SEC-3](../findings/2026-07-26-product-surface-sweep.md) navngiver roden: der er ingen
perimeter, og compose publicerer alt på `0.0.0.0`. Fundets egen formulering er præcis om truslen
— *"publishes on `0.0.0.0` by default, so this is LAN-reachable, not loopback-only."*
Truslen er **LAN, ikke loopback**. Det afgør hvilken af de to mulige indgreb der er det rigtige;
se Steps.

STATUS.md kalder denne halvdel *"ingen downside"*. **Det er kun sandt for det ene af de to
indgreb**, og forskellen er hele planen — se Risks.

Målt 2026-07-28 på kørende stak, ikke aflæst i compose-filen:

| Port | Aflæst |
|---|---|
| 5433, 5434, 5672, 15672, 9200, 6380, 11435 | alle `NÅELIG fra LAN` (192.168.1.199) |
| ES `_cat/indices` fra LAN, uden auth | `transactions_v2` **642 docs**, `accounts_v1` **292**, `goals_v1` 27, `taxonomy_v1` 52 |
| RabbitMQ mgmt fra LAN, `guest:guest` | `/api/overview` → fuld admin, RabbitMQ 3.13.7 |

Det er altså rigtige brugerdata, ikke en åben port uden indhold. Severity bekræftet ved
måling.

## Non-goals

- **Perimeter-ADR'en skrives ikke her.** P3-24's dyre halvdel (er gatewayen en
  sikkerhedsgrænse?) blokerer P3-25 og P2-27 og kræver en beslutning om ti origins,
  HttpOnly-cookie og CSP. Denne plan tager kun det indgreb der er rigtigt *uanset* hvordan
  ADR'en lander.
- **Service-portene 8001–8012 røres ikke.** Frontenden i browseren taler direkte til dem
  (`frontend/src/config/serviceUrls.js`), og e2e's health-gate poller dem. At lukke dem er
  ADR-arbejde, ikke dette.
- **Ingen credentials roteres.** `guest:guest`, `xpack.security.enabled: "false"` og
  Postgres-passwords i compose bliver som de er. Denne plan fjerner *rækkevidden*, ikke
  svagheden — se Risks.
- **Ingen adfærd i services ændres.** Ingen kode i `services/*/app/` røres. Container-til-
  container-trafik går over compose-netværkets DNS og er upåvirket af `ports:`.
- **`docker-compose.monitoring.yml` røres ikke** — verificeret: Prometheus rammer
  `postgres:5432`, `prometheus:9090`, `cadvisor:8080`, altså container-DNS, ikke host-porte.

## Steps

### Valget mellem to indgreb

**A — loopback-bind:** `"5434:5432"` → `"127.0.0.1:5434:5432"`. Fjerner LAN-rækkevidden,
beholder host-rækkevidden.
**B — slet `ports:` helt.** Fjerner begge.

**Planen bruger A.** Grunden er ikke bekvemmelighed, men at A rammer præcis den egenskab
fundet navngiver, mens B derudover river seks host-side-forbrugere over — som alle er
legitime og hvoraf én kører i CI:

| Forbruger | Port | Note |
|---|---|---|
| `tests/e2e/test_budget_month_closed_e2e.py:40` | 15672 | publicerer `budget.month_closed` via mgmt-API. **Kører i CI** (`ci.yml:336`) |
| `scripts/cleanup_pg_duplicates.py:84` | 5434 | maintenance-script, brugt i P2-25 |
| `scripts/backfill_category_names.py:54,56` | 5435, 5672 | |
| `services/ai-service/tests/eval/{es_seed.py:31,conftest.py:118}` | 9200 | `make test-eval` |
| `services/ai-service/Makefile:29` | 11435 | Ollama til eval |
| `services/banking-service/alembic.ini:4` | 5439 | |
| `docs/categorization-baseline.md:30` | 5434 | psql-kommando i docs |

B ville altså koste en migration af alle syv til `docker compose exec` plus en
compose-override — for en egenskab (loopback lukket) som fundet ikke beder om. Det er
omkostning uden det tilsvarende udbytte.

**A's accepterede omkostning, eksplicit:** enhver proces på selve maskinen — inkl. anden
software brugeren kører — kan stadig nå datastores uden auth. Vi accepterer det, fordi
alternativet ikke fjerner den svaghed alligevel (credentials er stadig `guest:guest`), og
fordi maskinen er en enkeltbruger-udviklingsmaskine. Den *rigtige* lukning af den rest er
credential-rotation, ikke port-fjernelse — noteres som opfølgning, ikke gøres her.

### Selve arbejdet

1. [x] **`docker-compose.yml` — præfiks `127.0.0.1:` på de 14 datastore-mappings.**
   Linjer: 46 (redis 6380), 61 (postgres 5433), 74–75 (rabbitmq 5672, 15672), 95 (es 9200),
   108 (ollama 11435), 166 (5438), 269 (5434), 335 (5436), 448 (5435), 566 (5437), 678 (5439),
   892 (5440), 995 (5441). Diff-form: én linje hver, kun præfiks tilføjet. **De ni
   service-mappings røres ikke.**
2. [x] **Kommentar over blokken** der siger *hvorfor* loopback og ikke sletning — så næste
   sweep ikke "retter" det tilbage til `0.0.0.0` eller videre til slettet uden at kende valget.
3. [x] **Verifikation** — se nedenfor. Egen commit hvis der skal rettes noget undervejs.

### Verification

Måling, ikke aflæsning. Alle tre led skal holde:

1. **Egenskaben er opnået:** `nc -z 192.168.1.199 <port>` fejler for alle 14; samme port på
   `127.0.0.1` lykkes. Plus negativ-test på data: ES `_cat/indices` og RabbitMQ `/api/overview`
   fra LAN-IP'en skal nu fejle, hvor de før returnerede 642 docs / fuld admin.
2. **Indgrebet kan blive rødt (kontrol):** rul præfikset tilbage på **én** port, vis at den
   igen er LAN-nåelig, sæt det på igen. Uden dette led måler vi kun at `nc` kan fejle —
   fx fordi stakken var nede.
3. **Intet er brækket:** `make test-e2e` (inkl. den 15672-afhængige test), plus
   `python scripts/cleanup_pg_duplicates.py --dry-run` og `psql` mod 5434 fra hosten.
   `docker compose ps` skal vise samme antal healthy containere som før.

## Risks & rollback

- **Største risiko: at "ingen downside" tages for pålydende og B vælges i farten.** Så bliver
  e2e rød i CI på en ændring der ser ud som ren compose-kosmetik. Modtrækket er tabellen
  ovenfor plus verifikationens led 3.
- **`127.0.0.1` dækker ikke IPv6.** Compose viser i dag også `[::]:PORT`. Hvis `nc` mod en
  LAN-IPv6-adresse stadig svarer efter ændringen, er egenskaben ikke opnået, og bindingen skal
  være `127.0.0.1` *og* `::1` — eller Docker skal konfigureres til ikke at publicere IPv6.
  **Dette tjekkes eksplicit i led 1**, ikke antaget.
- **Restsvaghed, bevidst efterladt:** credentials er uændrede. Ændringen flytter angrebsfladen
  fra "alle på LAN'et" til "alt på maskinen" — en reel forbedring, ikke en lukning.
- **Rollback:** ét `git revert`. Ingen migration, ingen state, intet schema. Compose-ændringer
  træder først i kraft ved `docker compose up -d`, så en fejl er synlig med det samme og
  påvirker ikke kørende containere før genstart.

## Outcome

**Shipped 2026-07-28 i `5ea37f0d`.** Én commit, kun `docker-compose.yml`: 14 port-mappings
præfikset `127.0.0.1:` plus en kommentar-blok der bærer valget. Ingen kode, ingen migration,
ingen adfærdsændring. **CI grøn på `baeb663f`** (run `30360964811`) — alle 19 jobs, og
E2E-jobbet gav 24 passed med de tre `test_budget_month_closed`-tests navngivet PASSED.

### Målingen

| | Før | Efter |
|---|---|---|
| Datastore-porte nåelige fra 192.168.1.199 | **14 / 14** | **0 / 14** |
| Samme porte på 127.0.0.1 | 14 / 14 | **14 / 14** |
| ES `_cat/indices` fra LAN, uden auth | `transactions_v2` 642, `accounts_v1` 292, +2 | `curl` exit 7 |
| RabbitMQ mgmt fra LAN, `guest:guest` | fuld admin, 3.13.7 | `curl` exit 7 |
| Service-porte 8001–8012 | `0.0.0.0` | `0.0.0.0` (urørt, som planlagt) |

**Kontrollen kørte og var rød.** ES alene rullet tilbage til `0.0.0.0`, container genskabt:
de 642 docs igen læsbare fra LAN-IP'en. Præfiks sat på igen: refused. Uden det led ville
sweepet kun have vist at `nc` *kan* fejle — fx fordi stakken var nede.

**IPv6-risikoen bortfaldt af sig selv, men blev tjekket.** `[::]:PORT`-bindingerne forsvandt
sammen med `0.0.0.0`-halvdelen; `nc -6` mod en global ULA (`fd99:d826:…`) på 9200/5434/15672
gav lukket, og `lsof -sTCP:LISTEN` viser socket'en på `127.0.0.1` alene. Planen antog at det
kunne kræve en `::1`-binding oveni. Det gjorde det ikke.

### Deviations

**Ingen på indgrebet.** Valget A vs. B holdt: alle syv host-side-forbrugere kørte uændret
efter (`test_budget_month_closed` via mgmt-API'et på 15672, begge scripts dry-run mod
5434/5435/5672, psql mod 5434 + 5439, Ollama 11435, ES 9200). Havde planen fulgt backloggens
"remove host publishing", var mindst CI-testen blevet rød.

**Én procesfejl undervejs, værd at have i loggen.** Første e2e-kørsel gav 17 passed / 7 errors
med `InterfaceError: connection is closed` fra transaction-service. Det var **ikke** bindingen:
jeg havde genskabt Postgres-containerne under kørende app-services, så deres asyncpg-pools
holdt døde forbindelser. Efter `docker compose restart` af app-laget: **24 passed** — præcis
STATUS.md's kendte baseline. Lektien er om rækkefølge ved compose-ændringer på datastores, ikke
om ændringen.

**Og [pipe-fælden ramte igen](../../CLAUDE.md), 6. gang.** Kontrollens første aflæsning var
`curl … | head -3 && echo "KONTROL RØD"` — `head` gør exit-koden 0, så beskeden fyrede mens
curl intet returnerede. Jeg var ét sekund fra at notere en kontrol som bestået, der ikke var
kørt: ES var bare ikke startet endnu. Gentaget uden pipe og med eksplicit `rc`-tjek blev den
faktisk rød. **Det er den samme fejlklasse som allerede står i CLAUDE.md's standing traps** —
og den overlever tilsyneladende at være skrevet ned.

### Follow-ups

- **P3-24's anden halvdel står åben** — perimeter-ADR'en. Denne plan rørte den ikke, og
  P3-25/P2-27 er stadig blokeret af den.
- **Restsvagheden er credentials, ikke porte.** `guest:guest`, `xpack.security.enabled: "false"`
  og Postgres-passwords i klartekst i compose. Alt *på* maskinen — inkl. enhver container via
  Docker Desktops `host.docker.internal`, verificeret — når stadig datastores uden auth.
  Fortjener eget item hvis systemet nogensinde flytter fra enkeltbruger-udviklingsmaskinen.
- **Rækkefølge-fælden bør stå i STATUS.md's standing traps:** genskaber man datastore-
  containere under kørende app-services, ser man pool-fejl der ligner en regression.
