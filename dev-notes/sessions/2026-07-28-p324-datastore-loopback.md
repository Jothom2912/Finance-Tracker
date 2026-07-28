# Session — 2026-07-28 · P3-24's datastore-halvdel

**Shipped:** `5ea37f0d` (compose), forudgået af `869a8825` (STATUS.md-rettelse).
**Plan:** [2026-07-28-p324-datastore-loopback-bind.md](../plans/2026-07-28-p324-datastore-loopback-bind.md)

## Hvad der skete

Sessionen startede som en opsummering. Den fandt to forældede påstande i STATUS.md — "CI er
ikke kørt endnu" (den var grøn på `880138f7`, run `30358915496`) og "Fire commits" om P2-29,
hvor der var fem. Rettet i `869a8825` før noget nyt blev startet.

Derefter P3-24's billige halvdel, valgt fordi STATUS.md kaldte den "ingen downside".

## Det påstanden ikke holdt

**Backloggen sagde "remove host publishing … has no downside".** Sweepet fandt syv host-side-
forbrugere af netop de porte:

| Forbruger | Port |
|---|---|
| `tests/e2e/test_budget_month_closed_e2e.py:40` — **kører i CI** | 15672 |
| `scripts/cleanup_pg_duplicates.py:84` | 5434 |
| `scripts/backfill_category_names.py:54,56` | 5435, 5672 |
| `services/ai-service/tests/eval/{es_seed.py,conftest.py}` | 9200 |
| `services/ai-service/Makefile:29` | 11435 |
| `services/banking-service/alembic.ini:4` | 5439 |
| `docs/categorization-baseline.md:30` | 5434 |

Fundets egen formulering afgjorde sagen: *"publishes on `0.0.0.0` by default, so this is
**LAN-reachable, not loopback-only**"*. Truslen er LAN. `127.0.0.1:`-præfiks rammer den
egenskab og lader alle syv stå. Sletning ville have kostet en migration af dem alle — og gjort
CI rød — for en egenskab fundet ikke beder om. Rubrikken i BACKLOG.md er rettet frem for at
stå.

## Målingen

Alt målt på kørende stak, ikke aflæst i compose-filen.

| | Før | Efter |
|---|---|---|
| Porte nåelige fra 192.168.1.199 | 14 / 14 | **0 / 14** |
| Samme på 127.0.0.1 | 14 / 14 | 14 / 14 |
| ES `_cat/indices` fra LAN, uden auth | `transactions_v2` **642**, `accounts_v1` **292** | exit 7 |
| RabbitMQ mgmt fra LAN, `guest:guest` | fuld admin, 3.13.7 | exit 7 |
| Service-porte 8001–8012 | `0.0.0.0` | `0.0.0.0` (urørt) |

Det var altså rigtige brugerdata på et åbent LAN, ikke en tom port.

**Kontrol:** ES alene rullet tilbage til `0.0.0.0`, container genskabt → de 642 docs igen
læsbare fra LAN. Præfiks på igen → refused. **IPv6:** `[::]`-bindingerne forsvandt sammen med
`0.0.0.0`; `nc -6` mod en global ULA på 9200/5434/15672 gav lukket, og `lsof -sTCP:LISTEN`
viser `127.0.0.1` alene. Planen havde afsat plads til at det kunne kræve en `::1`-binding. Det
gjorde det ikke.

**Intet brækket:** `make test-e2e` 24 passed inkl. den 15672-afhængige test; begge scripts
dry-run; psql mod 5434 + 5439; Ollama 11435 (6 modeller); ES 9200 green.

## To fejl jeg lavede, værd at have skrevet ned

**1. Pipe-fælden, 6. gang — og den ramte selve kontrollen.** Første aflæsning var
`curl … | head -3 && echo "KONTROL RØD som forventet"`. `head` gør exit-koden 0, så beskeden
fyrede mens curl intet returnerede. Jeg var ét sekund fra at notere en kontrol som bestået, der
ikke var kørt — ES var bare ikke startet endnu. Gentaget med eksplicit `rc=$?` og retry-loop
blev den faktisk rød. **Fælden står allerede i CLAUDE.md's standing traps og overlevede at
være skrevet ned.** Det er argumentet for at gøre den mekanisk frem for at gentage advarslen.

**2. Genstartsrækkefølgen så ud som en regression.** Første e2e-kørsel gav 17 passed / 7 errors
med `InterfaceError: connection is closed` fra transaction-service. Jeg havde genskabt
Postgres-containerne under kørende app-services, så asyncpg-poolene holdt døde forbindelser.
`docker compose restart` af app-laget → 24 passed. Havde jeg konkluderet på første kørsel,
ville ændringen være blevet rullet tilbage for en fejl den ikke forårsagede. Tilføjet som
standing trap.

## Open ends

- **P3-24's ADR står stadig.** Den er nu det billigste træk der oplåser to items (P3-25, P2-27),
  og kan ikke skæres mindre — kernen er de ti browser-origins.
- **Credentials er urørte.** `guest:guest`, `xpack.security.enabled: "false"`, Postgres-
  passwords i klartekst i compose. Verificeret at enhver container stadig når hosten via
  `host.docker.internal:5434`. Angrebsfladen er flyttet fra "alle på LAN'et" til "alt på
  maskinen" — ikke lukket. Fortjener eget item hvis systemet forlader udviklingsmaskinen.
- ~~CI ikke kørt~~ — **grøn på `baeb663f`** (run `30360964811`), alle 19 jobs. E2E-jobbet
  kørte og gav **24 passed**, og de tre `test_budget_month_closed`-tests står navngivet som
  PASSED i loggen. Det er den egentlige kvittering på valg A: den ene host-side-forbruger der
  kører i CI, taler til RabbitMQ-mgmt på 15672 og gør det stadig med loopback-binding. Havde
  planen fulgt backloggens "remove host publishing", var netop de tre blevet røde her.
