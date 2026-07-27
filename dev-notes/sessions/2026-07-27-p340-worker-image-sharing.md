---
date: 2026-07-27
topic: P3-40 — workers deler API-servicens image; A/B mod den kommando der lyver
---

# Session 2026-07-27 — P3-40 worker image sharing

## Done

- `f3534abb` — `name: finance-tracker` pinnet, eksplicit `image:` på de 12 API-services,
  de 26 workers skiftet fra `build:` til `image: finance-tracker-<api-svc>`.
- `f42d0a43` — `scripts/compose_check.py` + `make compose-check` + CI-step i `repo-lint` +
  pre-commit-gate når `docker-compose.yml` er staged.
- Notes: plan lukket med Outcome, finding → `resolved`, backlog-rækken → done,
  STATUS.md + 00-INDEX.md opdateret.
- E2E 24/24, stack 51/51 running efter fuld rebuild + `--force-recreate`.

## Learned / surprised

- **k8s gjorde det allerede rigtigt.** Hver manifest i `k8s/workers/` peger på
  `finance-tracker/<svc>:local` — ét image per service, bygget af
  `scripts/build-k8s-images.sh`. Compose var outlieren, ikke normen. Det ændrede opgaven fra
  "vælg et design" til "bring compose på linje med husets egen praksis", og det er værd at
  huske som søgemønster: **når to deployment-targets er uenige, så tjek hvilket der er
  konsistent med resten før du designer et tredje svar.**
- **Kontrollen var det eneste der beviste noget.** Jeg kørte det samme kommandopar mod
  `HEAD~2:docker-compose.yml` (via `-f ... --project-directory .`) og mod den nye fil:
  build exit 0, up exit 0, `running` i begge — 0 markør-hits i kontrollen, 1 i treatment.
  Uden kontrollen ville treatment-resultatet have været forenelig med "det virkede altid".
  For et item hvis fejlmode *er* en grøn verifikation, er A/B ikke overdrevet, det er
  minimum.
- **Gaten fangede sin egen forfatter.** Første kørsel af pre-commit-hooken efter jeg havde
  skrevet `compose_check.py` fejlede — på at `compose_check.py` selv ikke var ruff-formateret.
  Billigste mulige demonstration af at hooken virker.
- **`[ a ] || [ b ] && exit 1` er en fælde under `set -e`.** Når begge checks *består*,
  exit'er &&-listen 1, og hele hooken afbrydes — dvs. gaten ville have blokeret rene commits.
  Fanget ved at køre hooken i alle fire tilstande i stedet for kun den fejlende. Generelt:
  **afprøv en gate i den tilstand hvor den skal tie, ikke kun i den hvor den skal råbe.**
- 56 → 44 images, men de 25 forældreløse worker-tags **forsvinder ikke af sig selv**: de er
  taggede, så `docker image prune` rører dem ikke. De er inerte (intet i compose refererer
  dem), ikke stale. Kræver eksplicit `docker image rm`; overladt til brugeren.

## Open ends

- **`docker image rm` af de 31 forældreløse tags** (25 worker-tags + 6 fra services slettet i
  juni: `monolith`, `*-sync-consumer`, `categorization-category-sync`). Rent diskforbrug,
  ingen hast — men det er nu bare cruft, ikke noget compose kan finde på at bruge.
- **P3-17 er stadig åben** og er samme rod: workers overrider `command:` og springer derfor
  de migrations over der kører i API'ets `CMD`. P3-40 tog image-halvdelen af "workers er
  andenrangs i compose-filen"; migration-halvdelen står tilbage.
- **P2-21's CI-check har nu et hjem.** `scripts/compose_check.py` er stedet at lægge
  compose-vs-kustomization-diffen, frem for et andet script ved siden af.
- Næste item efter STATUS.md: **P2-25** (transaction soft-delete — beslutning før kode,
  gater P3-37).

## Notes updated

- Ny: `plans/2026-07-27-p340-worker-image-sharing.md`, denne session-log.
- Opdateret: `findings/2026-07-25-per-worker-image-staleness.md` (resolved),
  `backlog/BACKLOG.md` (P3-40 done), `STATUS.md`, `00-INDEX.md`, `sessions/00-SESSIONS.md`.
