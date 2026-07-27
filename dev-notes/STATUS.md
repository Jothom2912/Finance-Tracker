# Status — 2026-07-28 (efter P3-23)

Where the work stands right now. **Read this first**; it exists so a session does not start
by guessing which of 32 plans is live. Update it when the active plan changes, an item
finishes, or a session ends — a stale STATUS.md is worse than none.

Everything here is derivable from the backlog and plan statuses; this file is a shortcut,
not a second source of truth. If it disagrees with `backlog/BACKLOG.md`, the backlog wins.

## Active

**Intet aktivt item.** P3-23 lukkede 2026-07-28. Næste item er ikke valgt — se **Next up**.

Sidst shippet: **P3-23** (2026-07-28) — banking-service på uv + pyproject, med lockfile,
dev/runtime-split og på typecheck-gaten (**9 af 12**; install-sti **11 af 12**). Fire commits:
`6e9c8bda` (pyproject + `uv.lock`, `requirements.txt` slettet, `python-jose` ud af runtime),
`6a998bc0` (Dockerfile på `uv sync --frozen --no-dev`), `0fd25d59` (mypy-gaten), + docs.
Udbyttet gentog P2-31's mønster: de 31 første mypy-fejl var **fire allerede kendte kontrakt-items**
(P2-32/33/35/36) plus fem ægte annotations-fejl — ingen nye bugs.
Runtime-verificeret lokalt: `app.main` + alle fire worker-moduler importerer under imagets
fastapi 0.140.7, container op, alembic kørt, alle fire workers forbundet til RabbitMQ.
**CI har ikke kørt på dette endnu** — se `make ci-status`.
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

- **P2-25** — transaction soft-delete + gone-vs-not-yet i categorization-write-backen (den
  eneste P2 der er en data-model-beslutning, så den gater P3-37).
- **P2-21** — k8s manifest drift: 6 workloads + 1 DB i compose har ingen manifest, så
  `apply -k` taber notification-feeden og den automatiske ADR-0003-kæde i stilhed.
  CI-check-halvdelen er nu billigere: `scripts/compose_check.py` er stedet at lægge
  compose-vs-kustomization-diffen, og P2-37 har allerede udvidet den fil fra "compose-check" til
  build hygiene — så der er præcedens for en tredje regel, men også en optjent omdøbning til
  `build_hygiene_check.py` at gøre først.
- **P2-27/28/29** — rate limiting, taxonomy write auth, CSV upload bounds. Alle fra
  product-surface-sweepet; hver er lille og uafhængig.

Ikke akut, selvom titlen lyder sådan: **P2-36** (`x-retry-count` → uendelig redelivery) — hver
writer i repoet sætter en `int`, så `str`-grenen nås ikke af vores egne republishes. Hærdning.

**P2-32/33/35/36 har nu hver et fodfæste i banking.** P3-23 efterlod dem som
`# type: ignore[...]  # P2-3x` (grep dem frem med `grep -rn 'ignore\[' services/banking-service/app`).
`warn_unused_ignores` er slået til, så **den service der fejler når et af de fire items fixes,
er banking** — det er ikke en regression, det er kvitteringen. Fjern ignoren i samme commit.

## Open findings worth knowing before you touch anything

| Finding | Severity | Scheduled as |
|---|---|---|
| [product-surface sweep](findings/2026-07-26-product-surface-sweep.md) | HIGH | P2-26..29, P3-24..34, F2-08..13 |
| [k8s manifest drift](findings/2026-07-25-k8s-manifest-drift.md) | MEDIUM | P2-21 |
| [transaction hard-delete → DLQ](findings/2026-07-25-transaction-hard-delete-categorized-dlq.md) | MEDIUM | P2-25 |
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
