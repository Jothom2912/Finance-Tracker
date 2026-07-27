# Status — 2026-07-28 (efter P2-31)

Where the work stands right now. **Read this first**; it exists so a session does not start
by guessing which of 32 plans is live. Update it when the active plan changes, an item
finishes, or a session ends — a stale STATUS.md is worse than none.

Everything here is derivable from the backlog and plan statuses; this file is a shortcut,
not a second source of truth. If it disagrees with `backlog/BACKLOG.md`, the backlog wins.

## Active

**Intet aktivt item.** P2-31 lukkede 2026-07-27 og efterlod en klynge på seks nye items
(P2-32…P2-37) plus et efterslæb i noterne, som er ryddet 2026-07-28. Næste item er ikke valgt —
se **Next up**, hvor rækkefølgen nu har en begrundelse den ikke havde før.

Sidst shippet: **P2-31** (2026-07-27) — mypy som hård gate på **8 af 12** services, styret af
`TYPECHECK_SERVICES` i `ci.yml`. CI grøn på `36428508` (run `30308332057`). Verificeret som
kontrol via `make verify-typecheck-gate` (8 gatede / 4 ikke-gatede, bevist i stand til at blive
rød) — en grøn step-conclusion beviser intet, da steppet kører for alle 12.
[Plan + Outcome](plans/2026-07-27-p231-static-typecheck-gate.md#outcome) ·
[session-log](sessions/2026-07-27-p231-typecheck-gate.md).

Udbyttet var **usande kontrakter, ikke typefejl** — det er derfor de seks nye items er
kontrakt-items og ikke oprydning.

## Next up

Den samlende tråd for de to øverste er **én install-sti per service**; de er samme arbejde
anvendt på hver sin service, og tilsammen lukker de hullet P2-31 efterlod.

- **P2-37** — budget-service på `uv sync --frozen` som de 9 andre. Målt 2026-07-28: drift
  mellem `requirements.txt` og `uv.lock` er mulig i **præcis én** service, og det er den der
  udstedte en død container fra en grøn gate. Fixet fjerner fejlklassen frem for at overvåge
  den, og `freeze`-præmissen i den oprindelige beskrivelse var usand ([detail](backlog/BACKLOG.md#p2-37)).
- **P3-23** — banking-service på uv + pyproject. Uden den kan banking ikke komme på
  typecheck-gaten, altså **beskytter P2-31 ikke den service hvor fejlen var**. Giver samtidig
  banking en lockfile (P2-37's form) og et sted at låse P3-26's sårbare pins.
- **P2-25** — transaction soft-delete + gone-vs-not-yet i categorization-write-backen (den
  eneste P2 der er en data-model-beslutning, så den gater P3-37).
- **P2-21** — k8s manifest drift: 6 workloads + 1 DB i compose har ingen manifest, så
  `apply -k` taber notification-feeden og den automatiske ADR-0003-kæde i stilhed.
  CI-check-halvdelen er nu billigere: `scripts/compose_check.py` er stedet at lægge
  compose-vs-kustomization-diffen — og P2-37's vagt hører samme sted.
- **P2-27/28/29** — rate limiting, taxonomy write auth, CSV upload bounds. Alle fra
  product-surface-sweepet; hver er lille og uafhængig.

Ikke akut, selvom titlen lyder sådan: **P2-36** (`x-retry-count` → uendelig redelivery) — hver
writer i repoet sætter en `int`, så `str`-grenen nås ikke af vores egne republishes. Hærdning.

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

- `account-service` and `banking-service` are pip-based with no venv: `make test` / `make lint`
  fail locally regardless of the code. banking's suite runs **only** in CI. See P3-39.
- Never pipe a verification command through `tail`/`head` — the pipeline's exit code is the
  last command's, so `check | tail && git commit` commits on a failing check.
- **Workers are still second-class in compose**: P3-40 fixed the *image* half, but P3-17 is
  open — workers override `command:` and so skip the migrations that run in the API's `CMD`.
- **En grøn `make check` er ikke et løfte om at containeren starter.** `uv.lock` styrer tests
  og typecheck; budget-services image `pip install`er `requirements.txt`. Se P2-37.
- **`tests/` er ikke typechecket** på nogen af de 8 gatede services (`packages = ["app"]`), og
  de 4 udenfor er slet ikke dækket — antag ikke at en typefejl er fanget i goal, banking,
  account eller gateway.
- **`make notes-check` verificerer mekanik, ikke sandhed.** Den var grøn mens denne fil sagde
  at P2-31 ikke var påbegyndt. Kandidater til at lukke det hul står i
  [session-loggen](sessions/2026-07-27-p115-p226-and-notes-infra.md) under Open ends.
- `make ci-status` for the current branch's CI; `make notes-check` before committing notes;
  `make compose-check` before committing `docker-compose.yml`.
