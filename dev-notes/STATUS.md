# Status — 2026-07-28 (efter P2-29)

Where the work stands right now. **Read this first**; it exists so a session does not start
by guessing which of 32 plans is live. Update it when the active plan changes, an item
finishes, or a session ends — a stale STATUS.md is worse than none.

Everything here is derivable from the backlog and plan statuses; this file is a shortcut,
not a second source of truth. If it disagrees with `backlog/BACKLOG.md`, the backlog wins.

## Active

**Intet aktivt item.** P2-29 lukkede 2026-07-28. Næste item er ikke valgt — se **Next up**.

Sidst shippet: **P2-29** (2026-07-28) — byte-, række- og transportgrænse på `/import-csv`.
Fem commits: `555ffd5e` (`CSV_MAX_BYTES`/`CSV_MAX_ROWS`, handler-guard før `.read()`,
rækkegrænse i `ParsedCSVResult.add_row` så de tre parsere deler én implementation),
`7f4c35ac` (`Content-Length`-middleware), `d0661ad1` (12 tests — endpointets **første**
adapter-dækning, integration 69 → 81), `4621ac2a` (frontend pre-flight),
`880138f7` (alembics `fileConfig()` slukkede appens loggere).
Ingen migration, intet schema rørt.

**OOM'en var virkelig, og det blev målt som kontrol.** `mem_limit: 512m` (k8s' tal) plus
`CSV_MAX_BYTES` hævet via env — samme image, én variabel ændret — gav
`OOMKilled=true, ExitCode=137` på en 150 MB upload. Med guarden på: 413 på 3 ms, RSS uændret
(82,26 → 82,41 MiB), container oppe. Hver guard er bevist i stand til at blive rød:
handler-guard fjernet → 2 røde, middleware → 1, rækkegrænse → 1.

**Planens egen disk-måling var et forkert instrument.** `du -sh /tmp` viste 4 KB mens 150 MB var
i luften, fordi `tempfile` bruger `O_TMPFILE` (unlinked, ingen directory-entry). `df -k` pollet
under uploaden: Content-Length-stien 0 MB, chunked-stien **137 MB**. Det accepterede chunked-hul
er dermed kvantificeret frem for kun navngivet.
[Plan + Outcome](plans/2026-07-28-p229-csv-upload-guards.md#outcome) ·
[session-log](sessions/2026-07-28-p229-csv-upload-guards.md).

**CI grøn på `880138f7`** (run `30358915496`) — altså på alle fem commits. Den femte var
nødvendig for at komme dertil: suiten var rød i CI på to push og grøn når testklassen kørte
alene. `fileConfig()` defaulter til `disable_existing_loggers=True`, så hver logger der fandtes
da migrationen kørte blev `.disabled = True` — og `categorized_consumer` importeres ved
collection, altså før `_migrated_db`. Adfærden var korrekt hele tiden; **kun sporet forsvandt**,
og testen asserterer på sporet. Import-rækkefølgen afgjorde det, ikke soft-delete-koden.

Den før det: **P2-25 + P3-37** (2026-07-28) — soft-delete på `transactions`. Fem commits:
`762e6c5b` (migration 013: `deleted_at` + det partielle external_id-index narrowet med
`AND deleted_at IS NULL`), `4deb9dac` (prædikater på alle læse-stier og begge dedup-queries;
`delete` stempler i stedet for at fjerne), `9a578fac` (ni integrationstests),
`3df1d778` (consumerens tredje gren), `2b59e77f` (`cleanup_pg_duplicates.py`).
P3-37 var aldrig et selvstændigt item — migrationen alene har ingen værdi, consumer-grenen alene
er umulig at skrive.

**Blast radius var mindre end frygtet, og det blev målt:** ES og analytics blev ikke rørt, fordi
projektionen allerede satte `is_deleted: true` og `_base_filters` allerede filtrerede på det.
Ændringen er transaction-service plus ét maintenance-script.

**Kontrollen korrigerede planens præmis.** Planen tilskrev DLQ-fixet consumer-grenen; med grenen
fjernet, men soft-delete på plads, fejler kun én af dens fire tests, fordi rækken nu *findes* og
der aldrig backes off. Soft-delete alene lukker DLQ-stien; grenen forhindrer at en tombstone får
sine kategoriseringsfelter overskrevet. Samme greb på repo-niveau: med prædikaterne fjernet fejler
7 af de 9 soft-delete-integrationstests.

Live-verificeret på fuld compose-stak: kolonnen og indexet aflæst i `\d transactions`
(ikke kun exit-kode 0), `total_count` faldt med præcis 1, `/analytics/overview` med præcis
rækkens beløb (500,00 → 0,00), ES-dokumentet `is_deleted: true`, re-import gav et nyt id, og
DLQ-reproduktionen kørt **med kontrol**: den slettede tx acker stille (DLQ 2 → 2, én INFO-linje),
mens et id der aldrig har eksisteret stadig backer off og lander i DLQ'en (2 → 3).
`make test-e2e` 24 passed.
[Plan](plans/2026-07-28-p225-transaction-soft-delete.md) ·
[decision](decisions/2026-07-28-transaction-soft-delete.md).

Den før det: **P3-23** (2026-07-28) — banking-service på uv + pyproject, med lockfile,
dev/runtime-split og på typecheck-gaten (**9 af 12**; install-sti **11 af 12**). Fire commits:
`6e9c8bda` (pyproject + `uv.lock`, `requirements.txt` slettet, `python-jose` ud af runtime),
`6a998bc0` (Dockerfile på `uv sync --frozen --no-dev`), `0fd25d59` (mypy-gaten), + docs.
Udbyttet gentog P2-31's mønster: de 31 første mypy-fejl var **fire allerede kendte kontrakt-items**
(P2-32/33/35/36) plus fem ægte annotations-fejl — ingen nye bugs.
Runtime-verificeret lokalt: `app.main` + alle fire worker-moduler importerer under imagets
fastapi 0.140.7, container op, alembic kørt, alle fire workers forbundet til RabbitMQ.
CI grøn på `e8865dcb` (run `30313411120`). Verificeret som **kontrol** via
`make verify-typecheck-gate`: **9 gated / 3 not gated**, og banking rapporterer `notice=no` —
altså at mypy faktisk kørte, ikke at steppet blev sprunget over.
[Plan + Outcome](plans/2026-07-28-p323-banking-uv-pyproject.md#outcome) ·
[session-log](sessions/2026-07-28-p323-banking-uv-pyproject.md).

Den før det: **P2-37** (2026-07-28) — budget-services image installerer fra `uv.lock` som de 9
andre, så tests, mypy og container læser samme fil. Tre commits: `560cd54a` (Dockerfile +
`requirements.txt` slettet), `8d7c8f59` (tre døde `freeze:`-targets), `18bd5fc8` (vagt i
`scripts/compose_check.py` mod at en service igen har begge filer, verificeret rød på både
transaction og budget). CI grøn på `d555f20e` — alle **19** jobs, inkl. E2E og det omdøbte
`Build-hygiene check`-step, som er rule 4's første kørsel i CI (run `30311338979`).
Runtime-beviset er lokalt: container op, alembic kørt, `app.main` importeret under fastapi
0.136.3 med alle tre 204-ruter, og alle tre workers oppe.
[Plan + Outcome](plans/2026-07-28-p237-budget-single-install-path.md#outcome) ·
[session-log](sessions/2026-07-28-p237-single-install-path.md).

Den før det: **P2-31** (2026-07-27) — mypy som hård gate på **8 af 12** services, styret af
`TYPECHECK_SERVICES` i `ci.yml`. CI grøn på `36428508` (run `30308332057`). Verificeret som
kontrol via `make verify-typecheck-gate`.
[Plan + Outcome](plans/2026-07-27-p231-static-typecheck-gate.md#outcome) ·
[session-log](sessions/2026-07-27-p231-typecheck-gate.md). Udbyttet var **usande kontrakter, ikke
typefejl** — det er derfor de seks items den affødte (P2-32…P2-37) er kontrakt-items og ikke
oprydning.

## Next up

- **P2-21** — k8s manifest drift: 6 workloads + 1 DB i compose har ingen manifest, så
  `apply -k` taber notification-feeden og den automatiske ADR-0003-kæde i stilhed.
  CI-check-halvdelen er nu billigere: `scripts/compose_check.py` er stedet at lægge
  compose-vs-kustomization-diffen, og P2-37 har allerede udvidet den fil fra "compose-check" til
  build hygiene — så der er præcedens for en tredje regel, men også en optjent omdøbning til
  `build_hygiene_check.py` at gøre først.
- **P2-27/28** — rate limiting og taxonomy write auth. Begge fra product-surface-sweepet.
  Bemærk at ingen af dem er så uafhængige som P2-29 var: P2-27's *placering* afhænger af P3-24
  (der er ingen perimeter i dag), og P2-28 kræver en beslutning om et rolle-begreb, som ikke
  findes nogen steder i kodebasen. P3-24's billige halvdel — fjern host-publishing for de ni
  Postgres-instanser, RabbitMQ, ES, Redis og Ollama — har ingen downside og oplåser P2-27.

Ikke akut, selvom titlen lyder sådan: **P2-36** (`x-retry-count` → uendelig redelivery) — hver
writer i repoet sætter en `int`, så `str`-grenen nås ikke af vores egne republishes. Hærdning.

**P2-32/33/35/36 har nu hver et fodfæste i banking.** P3-23 efterlod dem som
`# type: ignore[...]  # P2-3x` (grep dem frem med `grep -rn 'ignore\[' services/banking-service/app`).
`warn_unused_ignores` er slået til, så **den service der fejler når et af de fire items fixes,
er banking** — det er ikke en regression, det er kvitteringen. Fjern ignoren i samme commit.

## Open findings worth knowing before you touch anything

| Finding | Severity | Scheduled as |
|---|---|---|
| [product-surface sweep](findings/2026-07-26-product-surface-sweep.md) | HIGH | P2-26..29 (**29 lukket**), P3-24..34, F2-08..13 |
| [k8s manifest drift](findings/2026-07-25-k8s-manifest-drift.md) | MEDIUM | P2-21 |
| [outbox-port erklærer fremmed entitet](findings/2026-07-27-outbox-port-declares-foreign-entity.md) | MEDIUM | P2-32 (7 services) |
| [Optional id skjuler upersisteret entitet](findings/2026-07-27-optional-id-hides-unpersisted-entity.md) | MEDIUM | P2-35 |
| [goal: `Goal` har to runtime-typer](findings/2026-07-27-goal-entity-two-runtime-types.md) | MEDIUM | P2-34 (blokerer goal for gaten) |
| [x-retry-count læst fem måder](findings/2026-07-27-retry-header-read-five-ways.md) | MEDIUM | P2-36 (ikke live i dag) |
| [INTERNAL_API_KEY optional-men-obligatorisk](findings/2026-07-27-internal-api-key-optional-but-mandatory.md) | LOW | P2-33 (6 services) |
| [131 bare mocks uden `spec`](findings/2026-07-27-sync-trigger-double-value.md) | MEDIUM | P3-41 — nu det største usikrede areal, da `tests/` er uden for mypy-scope |
| [worker migration ordering](findings/2026-07-25-worker-migration-ordering.md) | LOW | P3-17 |
| [eval seed writes to prod index](findings/2026-07-26-eval-seed-writes-to-prod-index.md) | LOW | P3-21 |
| [non-UUID saga_id poison](findings/2026-07-25-saga-reply-non-uuid-poison.md) | LOW | P3-19 |

## Standing traps

- `account-service` is pip-based with no venv: `make test` / `make lint` fail locally regardless
  of the code, and repo-wide `make lint`/`make check` abort on it before reaching the other
  eleven. See P3-39 (banking's half closed by P3-23; its suite now runs locally, 68 passed).
- Never pipe a verification command through `tail`/`head` — the pipeline's exit code is the
  last command's, so `check | tail && git commit` commits on a failing check.
- **Workers are still second-class in compose**: P3-40 fixed the *image* half, but P3-17 is
  open — workers override `command:` and so skip the migrations that run in the API's `CMD`.
- **En grøn `make check` er stadig ikke et løfte om at containeren starter** — men grunden er
  ændret. Den *todelte* årsag (budgets image `pip install`ede `requirements.txt` mens tests læste
  `uv.lock`) er væk med P2-37, og `make compose-check` fejler nu hvis den kommer tilbage. Tilbage
  står at `check` er statisk: den importerer ikke `app.main` under imagets versioner. `account`
  har desuden stadig ingen lockfile, så for *den* er der ikke engang en fil at være enig med
  (P3-01). Det billige modtræk, brugt i både P2-37 og P3-23:
  `docker run --rm <image> python -c "import app.main"` plus samme import af hvert worker-modul.
- **`tests/` er ikke typechecket** på nogen af de 9 gatede services (`packages = ["app"]`), og
  de 3 udenfor er slet ikke dækket — antag ikke at en typefejl er fanget i goal, account
  eller gateway.
- **`make notes-check` verificerer mekanik, ikke sandhed.** Den var grøn mens denne fil sagde
  at P2-31 ikke var påbegyndt. Kandidater til at lukke det hul står i
  [session-loggen](sessions/2026-07-27-p115-p226-and-notes-infra.md) under Open ends.
- `make ci-status` for the current branch's CI; `make notes-check` before committing notes;
  `make compose-check` before committing `docker-compose.yml` **or adding a dependency file to a
  service** — den bærer nu to regler (worker-image-deling + én install-sti per service).
