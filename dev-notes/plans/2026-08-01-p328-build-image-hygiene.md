---
title: P3-28 — build- og image-hygiejne
date: 2026-08-01
status: done
backlog: [P3-28]
related:
  - ../findings/2026-07-26-product-surface-sweep.md
  - 2026-08-01-p347-nginx-header-inheritance-gate.md
  - 2026-07-28-p343-nginx-perimeter.md
---

# P3-28 — build- og image-hygiejne

## Goal

Docker skal ikke sende lokale miljøer, dependencies, Git-data eller kendte credentials ind i
den fælles build-context; uv-baserede runtime-images skal ikke beholde downloadcachen; og det
byggede frontend-image skal gzippe tekst-assets og cache hash-navngivne `/assets/` immutable
uden at miste perimeterens fire security headers. Resultatet bevises i byggede images og via
HTTP, ikke kun ved statiske checks.

## Context

[Produktsweepets OPS-1](../findings/2026-07-26-product-surface-sweep.md) fandt fire beslægtede
buildproblemer. Genmålt 2026-08-01: alle 13 Compose-builds bruger repo-roden som context; der er
stadig ingen `.dockerignore`; repoet fylder ca. 2,8 GB, frontendens `node_modules` ca. 246 MB og
service-venvs op til ca. 206 MB hver. Elleve Dockerfiles kører fortsat `uv sync --frozen
--no-dev` uden cachefravalg, og frontend-Dockerfilen kopierer hele servicekataloget efter
dependency-installationen. [P3-47](2026-08-01-p347-nginx-header-inheritance-gate.md#outcome-fill-in-when-done)
har nu gjort den nødvendige gentagelse af security headers maskinelt håndhævet, før asset-
locationen tilføjes.

## Non-goals

- Ingen frontend code splitting eller bundle-budget; det tilhører P3-30.
- Ingen multi-stage-refaktor af Python-images, base-image-opgraderinger eller dependency-
  ændringer.
- Ingen oprydning i udviklerens lokale `.venv`, `node_modules`, Docker-cache eller images.
- Ingen ændring af API-ruter, CSP-værdier, rate limits eller cachepolitik for `index.html` og
  SPA-ruter; kun Vites hash-navngivne `/assets/` får immutable caching.
- Ingen ændring af account-service og serverless-health-jobs eksisterende
  `pip --no-cache-dir`-installationer.

## Steps

1. [x] **Afgræns build-contexten.** Tilføj en root `.dockerignore`, fordi alle builds bruger
   `context: .`; ekskludér mindst `.git`, `.env*`, private key/certificate-formater,
   `**/.venv`, `**/node_modules`, Python/JS caches, test-output og editorfiler, men behold
   tracked eksempler som `.env.example`. Udvid `scripts/compose_check.py` og dens unit-tests
   med negative kontroller for de load-bearing mønstre, så en senere fjernelse ikke tavst gør
   contexts store eller credentials tilgængelige for `COPY`.
2. [x] **Fjern uv-downloadcache fra images.** Sæt `UV_NO_CACHE=1` i de elleve uv-baserede
   service-Dockerfiles, og tilføj en statisk compose-check, der finder et `uv sync` uden enten
   miljøflaget eller `--no-cache`. Lad pip-baserede images være urørte.
3. [x] **Gør frontend-builden deterministisk og smal.** Skift
   `services/frontend/Dockerfile` fra `npm install` til `npm ci`; root-ignorefilen sikrer, at
   den efterfølgende kildekode-`COPY` ikke kan overskrive Linux-dependencies med hostens
   `node_modules`. Bevar den eksisterende to-stage Node/nginx-form.
4. [x] **Komprimér og cache statiske assets sikkert.** Slå gzip til for relevante teksttyper i
   `services/frontend/nginx.conf`; tilføj en præcis `location /assets/` med `try_files`, ét års
   `public, immutable` cache og en eksplicit gentagelse af CSP, nosniff, frame- og
   referrer-headerne som krævet af P3-47. `index.html` og SPA-fallbacken forbliver uden
   immutable caching.
5. [x] **Statisk verifikation.** Kør `uv run --with pytest pytest -q
   tests/unit/test_compose_check.py`, `make compose-check`, frontendens `npm test`, `npm run
   lint` og `npm run build`, derefter `make notes-check` og `git diff --check`. Negative tests
   skal bevise både manglende ignore-mønster og en uv-installation, der igen beholder cache.
6. [x] **Image- og runtime-verifikation.** Mål før/efter på mindst frontend-imaget og ét
   repræsentativt uv-image; byg alle berørte images med Compose, start API'er, workers og
   frontend og inspicér logs/state. Bevis inde i uv-imaget, at `/root/.cache/uv` ikke ligger i
   slutlaget, og at delte pakker ikke indeholder `.venv`. Hent et hash-navngivet JS/CSS-asset
   gennem port 3000 med `Accept-Encoding: gzip` og bevis `Content-Encoding: gzip`, immutable
   cache samt alle fire security headers; hent `/index.html` som negativ kontrol uden
   immutable cache. Afslut med `make compose-state-check`.

## Risks & rollback

En for bred ignorefil kan fjerne en fil, som et Dockerfile faktisk kopierer; derfor bygges alle
13 images, og processerne startes bagefter. `npm ci` fejler med vilje, hvis lockfilen ikke
matcher manifestet, hvilket gør dependency-drift synlig før image-build. nginx-risikoen er
forkert location-match eller tabte headers; live headerkontroller plus P3-47 opdager begge.
Gzip kan øge CPU-forbruget lidt, men kun for komprimerbare frontend-assets; rollback er at
fjerne gzip-/asset-blokken, cacheflagene og ignore-gaten. Ingen persistent data eller schemaer
ændres.

## Outcome (fill in when done)

En root `.dockerignore` reducerer nu den fælles context ved at udelukke Git, lokale env-filer
og credentials, venvs, `node_modules`, caches og build/test-output, mens `.env.example`
bevares. Compose-check rule 8 fastholder de bærende ignore-mønstre og kræver cachefrie
`uv sync`-Dockerfiles. Alle elleve uv-images sætter `UV_NO_CACHE=1`; de to pip-baserede images
var allerede cachefrie og er urørte. Frontend-builden bruger nu lockfile-strikt `npm ci`.

Frontendens nginx gzipper CSS, JavaScript, JSON og SVG. Den nye præcise `/assets/`-location
giver Vites hash-assets `public, max-age=31536000, immutable`, afviser manglende assets med 404
og gentager de fire security headers som krævet af P3-47. HTML og SPA-ruter får ikke immutable
caching.

Verifikation 2026-08-01:

- `uvx ruff check` og `ruff format --check` på compose-check + tests: grønne;
  `uv run --with pytest pytest -q tests/unit/test_compose_check.py`: **10 passed**.
- Frontend `npm test -- --run`, `npm run lint`, `npm run build`: **352 passed**, lint og build
  grønne. De kendte React `act(...)`-warnings og P3-30s >500 kB chunk-warning består. Image-
  buildens `npm ci` rapporterede de allerede P3-26-ejede dependency-advisories.
- `docker compose build`: alle **13 lokale images** byggede. Build contexts blev målt til
  **32,43 kB** for frontend og 3,47 kB–1,05 MB for de viste Python-services, mod et lokalt
  arbejdstræ på ca. 2,8 GB.
- Repræsentativt goal-image: **198.005.034 → 98.873.683 bytes** (ca. 50 % mindre). En
  kortlivet container beviste både fravær af `/root/.cache/uv` og nul `.venv` under `/shared`.
  Frontendens runtime-image forblev som forventet ca. **22,1 MB**, fordi host-dependencies kun
  kunne påvirke build-staget.
- `docker compose up -d --wait` recreatede API'er, workers og frontend på de nye images. De
  seneste samlede logs havde ingen `ERROR`, `CRITICAL`, traceback eller exception.
- Live `GET /assets/index-B94L64AZ.js` med `Accept-Encoding: gzip`: 200,
  `Content-Encoding: gzip`, immutable cache og alle fire security headers. `GET /index.html`
  gav 200 + gzip + security headers, men ingen `Cache-Control`, som negativ kontrol.
- `make compose-state-check`: **62 containere**, ingen dead, exited nonzero eller restarting;
  kun de ti forventede migration/one-shot-containere exited cleanly.
- `make compose-check`, `make notes-check` og `git diff --check`: grønne ved afslutning.
