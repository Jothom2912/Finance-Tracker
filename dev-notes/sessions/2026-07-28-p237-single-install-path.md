---
date: 2026-07-28
topic: P2-37 — budget-services image læser uv.lock; hvorfor verifikationen skulle være runtime, og hvad den fandt gratis
---

# Session 2026-07-28 — P2-37 én install-sti per service

Trin-detaljerne og målingerne står i
[planen](../plans/2026-07-28-p237-budget-single-install-path.md) og dens Outcome. Denne log er
historien om hvordan det gik, og de lektier der ikke hører til ét enkelt trin.

## Done

- `560cd54a` — budget-services Dockerfile på `uv sync --frozen --no-dev`, `requirements.txt`
  slettet, de tre 204-kommentarer omskrevet fordi de påstod noget der ikke længere er sandt.
- `8d7c8f59` — tre døde `freeze:`-targets slettet (transaction, categorization, user).
- `18bd5fc8` — rule 4 i `scripts/compose_check.py`: en service må ikke have både `uv.lock` og
  `requirements.txt`. Docstring, `make help` og CI-stepnavnet omskrevet til build hygiene.
- Nyt item ud af arbejdet: **P3-42** (budgets `FastAPICache` er død infrastruktur).

## Learned / surprised

- **Den bedste verifikation var den vi ikke skrev.** Planen udpegede `httpx 0.27 → 0.28` som den
  bump ingen test kunne dække, fordi `respx` mocker transporten og derfor ikke ser en
  ægte-netværks-forskel. Den blev dækket alligevel: budget-alert-scheduleren ticker af sig selv og
  loggede rigtige `httpx`-kald til `analytics/overview` og categorization → 200 OK, sekunder efter
  `up -d`. Lektien er ikke "vi var heldige" — det er at **en service med kørende workers har en
  gratis integrationstest af sine udgående kald**, hvis man husker at læse deres logs frem for kun
  API'ets. Det er billigere end den e2e vi ellers havde skrevet.

- **En risiko kan skrumpe af den forkerte grund.** `redis 5 → 8` mod upinnet `fastapi-cache2` var
  planens mest sandsynlige inkompatibilitet. Den er reelt næsten ingen — men fordi **ingen rute er
  dekoreret med `@cache`**. `FastAPICache.init()` kaldes i lifespan, og så bruges cachen aldrig.
  Risikofladen var derfor kun `init` + `aclose()`. Værd at bemærke som mønster: da jeg gik for at
  *vurdere* en risiko, fandt jeg ud af at funktionaliteten bag den ikke findes. En risikoanalyse
  der ender i "det kan ikke gå i stykker, for det gør ikke noget" er et fund, ikke en betryggelse.
  → P3-42.

- **Samme fejl-*form* kan være tom i det konkrete tilfælde — men kun hvis man måler.** Den lokale
  venv kører py3.14, imaget py3.11. Det er præcis samme form som fejlklassen dette item lukker:
  tests og image på forskellige forudsætninger. Jeg tjekkede frem for at antage — locken har nul
  `python-version`-markers og ingen dublerede pakkenavne, så begge interpretere resolver til samme
  versionssæt. Formen er bekymrende, denne lock er det ikke. Havde jeg *antaget* det, havde jeg
  ikke haft belæg; havde jeg antaget det modsatte, havde jeg lavet unødigt arbejde.

- **Kommentarer om en fejl bliver usande når fejlen fixes.** De tre `response_model=None`-blokke
  sagde "FastAPI 0.115.0, hvad requirements.txt pinner, og derfor hvad imaget kører". Efter dette
  item findes hverken filen eller pinnet. Argumentet bliver stående, men grunden ændrer sig fra
  *load-bearing* til *eksplicit + værn mod en downgrade* — og den forskel skal stå i koden, ellers
  rydder nogen den op om seks måneder med god grund. En finding-reference i en kommentar aldrer
  ikke af sig selv.

- **En sletning kan være en sikkerhedsforanstaltning.** De tre `freeze:`-targets lignede oprydning.
  De er reelt tre knapper der kunne genskabe præcis den fejlklasse resten af itemet fjerner — i
  services der bygger med `--frozen` og ikke har nogen `requirements.txt`. Ingen af de tre
  pip-baserede services har nogensinde haft et, så det er ikke sådan deres filer blev til.

## Open ends

- **`account` og `banking` er stadig pip uden lockfile** (P3-23/P3-01). De kan ikke drifte — én
  usandt-låst kilde frem for to uenige — men konsekvensen er værd at sige højt: bankings
  `fastapi==0.115.0`-pin er den samme fælde budget lige havde, og den udløses den dag banking
  kommer på typecheck-gaten og nogen tilføjer et `-> None`.
- **`scripts/compose_check.py` hedder nu noget forkert.** Den bærer to regler, hvoraf den ene
  læser `services/*/` på disk. Valget var bevidst (vagtens værdi er at den *kører*, og scriptet er
  allerede wired i CI, `make` og pre-commit), men konsekvensen er en omdøbning til
  `build_hygiene_check.py` når nogen alligevel rører filen.
- **CI er ikke kørt** på de tre commits i skrivende stund — alt er verificeret lokalt, inkl. e2e.
  `make ci-status` efter push.
