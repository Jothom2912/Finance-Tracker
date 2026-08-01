---
title: P3-47 — vogt nginx security headers mod location-skygge
date: 2026-08-01
status: done
backlog: [P3-47]
related:
  - 2026-07-28-p325-p227-perimeter-headers-ratelimit.md
  - 2026-07-28-p343-nginx-perimeter.md
  - ../decisions/2026-07-28-nginx-as-perimeter.md
---

# P3-47 — vogt nginx security headers mod location-skygge

## Goal

`make compose-check` skal fejle, hvis en `location` i frontendens nginx-konfiguration sætter
sin egen `add_header` uden samtidig at gentage perimeterens fire security headers. En negativ
unit-test skal bevise den konkrete nginx-arveregel, før P3-28 tilføjer immutable asset-caching.

## Context

[P3-25-planen](2026-07-28-p325-p227-perimeter-headers-ratelimit.md#follow-ups) dokumenterer
fælden: nginx nedarver kun `server`-blokkens `add_header`-direktiver til locations, der ikke har
egne `add_header`-direktiver. P3-28 vil være den første legitime bruger af en location-lokal
header. Den eksisterende parser og perimeterkontrol i `scripts/compose_check.py` er den
kanoniske gate for nginx-konfigurationens tavse fejlformer.

## Non-goals

- Ingen `Cache-Control`, gzip eller øvrige P3-28-ændringer endnu.
- Ingen ændring af de fire security headers, deres værdier eller nginx' runtime-adfærd.
- Ingen generel nginx-parser; gaten understøtter fortsat repositoryets enkle, brace-baserede
  konfigurationsform og fejler højt på former, den ikke kan analysere.
- Ingen omdøbning af `compose_check.py` eller omnummerering af de eksisterende hovedregler;
  header-værnet er en femte assertion under rule 5, fordi det beskytter samme perimeterfil.

## Steps

1. [x] **Udvid nginx-parserens model.** Lad `scripts/compose_check.py` registrere
   `add_header`-navne på den `Location`, der ejer direktivet, uden at tælle server-blokkens
   globale headers som lokale.
2. [x] **Tilføj perimeter-assertionen.** Definér de fire krævede security-header-navne ét sted
   og rapportér location, linje og manglende navne, når en location har mindst én lokal header,
   men ikke hele sættet. Opdatér rule 5-dokumentationen og success-summary uden at ændre de
   eksisterende route-, upstream- eller Kustomize-checks.
3. [x] **Bevis positive og negative kontroller.** Udvid
   `tests/unit/test_compose_check.py` med en location uden lokale headers (tilladt), en location
   med `Cache-Control` alene (afvist med alle fire mangler) og en location, der gentager alle
   fire plus `Cache-Control` (tilladt).
4. [x] **Verifikation.** Kør `pytest -q tests/unit/test_compose_check.py`, `make compose-check`,
   `make notes-check` og `git diff --check`. Kør desuden testen med den negative fixture, så
   den røde kontrol er et parserbevis og ikke kun en assertion mod den aktuelle nginx-fil.

## Risks & rollback

Den største risiko er falsk tryghed fra forkert block ownership: en server-header må ikke blive
tilskrevet en location, og en nested blok må ikke lække tilbage til sin parent. De tre fixtures
gør begge sider synlige. Headernavne sammenlignes case-insensitivt, som HTTP kræver, så ren
kapitaliseringsdrift ikke giver en falsk fejl. Ændringen påvirker kun en statisk gate og kan
rulles tilbage ved at fjerne assertionen og dens tests; nginx-konfigurationen ændres ikke.

## Outcome (fill in when done)

`parse_nginx()` registrerer nu location-lokale headernavne case-insensitivt, og rule 5 kalder en
fokuseret assertion, der kun aktiveres for locations med mindst ét eget `add_header`. Manglende
security headers rapporteres deterministisk med location, linje og P3-47-reference. De fire
krævede navne ejes af én konstant; værdierne og den aktuelle nginx-konfiguration er urørte.

Tre fixtures beviser de afgørende grene: normal nedarvning uden lokal header passerer,
`Cache-Control` alene fejler med alle fire manglende navne, og `Cache-Control` plus det komplette
security-sæt passerer. Den eksisterende testfil gik fra fire til syv tests.

Verifikation 2026-08-01:

- `uv run --with pytest pytest -q tests/unit/test_compose_check.py`: **7 passed**. Repo-roden
  har bevidst intet pytest-miljø, så planens direkte `pytest` blev kørt gennem uv's ephemeral
  miljø; testindholdet var uændret.
- `make compose-check`: **62 services**, 20 nginx locations og 18 upstreams verificeret;
  security-header inheritance guarded; ingen problemer.
- `make notes-check` og `git diff --check`: grønne ved afslutning.
