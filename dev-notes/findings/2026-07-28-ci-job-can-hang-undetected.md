---
title: Et CI-job kan hænge i seks timer uden at nogen får det at vide — to manglende grænser i serie
date: 2026-07-28
severity: MEDIUM
status: open
scheduled-as: P2-38
related:
  - 2026-07-25-banking-ci-could-not-collect.md
  - ../sessions/2026-07-28-p325-p227-perimeter-hardening.md
---

# Et CI-job kan hænge i seks timer uden at nogen får det at vide

**Analytics-services `Run tests` hang 14 minutter og ville have hængt i op til 360, fordi der
ikke findes én grænse på vejen.** Opdaget 2026-07-28 på run `30381676420` — af at et menneske
kiggede, ikke af noget i systemet.

## Hvad der skete, målt

Loggen fra det hængte job:

```
17:10:53  collecting ... collected 123 items
17:24:49  ##[error]The operation was canceled.        <- manuel aflysning
```

123 tests collectet, og derefter **ikke én testlinje i 836 sekunder**. Sammenligning med den
foregående grønne kørsel (`30372244517`, to timer tidligere) placerer hængen præcist:

| | Grøn kørsel | Hængt kørsel |
|---|---|---|
| `collected 123 items` | 15:13:25 | 17:10:53 |
| Første test `PASSED` | 15:14:01 — **36 s** senere | aldrig, **836 s+** |
| Første test | `test_backfill.py::test_backfill_is_idempotent_and_resolves_names_from_taxonomy` | samme |

De 36 sekunder i den grønne kørsel **er** `es_container`-fixturen: pull og boot af
Elasticsearch. I den hængte kom containeren aldrig op.

**Det var en transient flake, og det er bevist frem for formodet:** en genkørsel af *samme
commit* uden en eneste kodeændring blev grøn. Havde årsagen ligget i ændringen, kunne den
genkørsel ikke være blevet grøn. Pushet rørte i øvrigt nul analytics- eller shared-filer.

## De to manglende grænser

Fejlen er ikke flaken. Flaken er uundgåelig. Fejlen er at **intet oversætter den til et
signal**:

1. **`services/analytics-service/tests/integration/conftest.py:19-24`** — den session-scopede
   `es_container`-fixture gør `with container:` på en `ElasticSearchContainer` uden nogen
   wait-timeout. testcontainers venter så på ES' readiness uden en øvre grænse.
2. **`.github/workflows/ci.yml`** — `grep -n "timeout-minutes"` giver **0 hits** i hele filen,
   så alle jobs arver GitHub Actions' default på **360 minutter**.

I serie betyder de to at en forbigående ES-fejl bliver en tavs flere-timers hæng frem for en
rød kørsel.

## Hvorfor det er værre end spildte runner-minutter

**Et hængende job er umuligt at skelne fra et langsomt job.** Det er samme klasse som
[banking-service's CI-job der aldrig kunne collecte sine tests](2026-07-25-banking-ci-could-not-collect.md)
og som de grønne kørsler der motiverede typecheck-gaten: en gate der ikke kan rapportere fejl.

Tre konkrete konsekvenser, alle observeret i denne hændelse:

- **Logs udleveres først når jobbet slutter.** `gh api .../logs` gav `BlobNotFound` (HTTP 404)
  mens jobbet kørte. Diagnosen krævede derfor at kørslen blev *aflyst* — altså at man først
  giver op, og dernæst undersøger.
- **Baselinen fandtes kun tilfældigt.** De 36 sekunder kunne aflæses fordi de fire foregående
  kørsler stadig lå i loggen. **Der er ingen alarm på varighed**, så der er ikke noget der
  ville have sagt "det her tager 13× for lang tid".
- **De øvrige 18 jobs var grønne**, så kørslen som helhed rapporterede `in_progress` i det
  uendelige — den tilstand der ligner "vent lidt" og betyder "aldrig".

## Fix-retning

Begge grænser, fordi den ene uden den anden kun flytter symptomet:

- `timeout-minutes` på jobbene i `ci.yml`. Sæt den ud fra målt varighed med rigelig margin
  (analytics-jobbet er ~1–2 min i dag), ikke ud fra et rundt tal. Effekten er at en hæng bliver
  **rød med en læsbar log** i stedet for usynlig.
- En eksplicit wait/startup-timeout på `es_container`. Den giver en fejlbesked der peger på ES
  frem for en pytest der bare tier — altså forskellen mellem "ES kom ikke op" og ingenting.

Overvej samtidig om `docker.elastic.co`-imaget skal caches i CI; registryet svarede fint fra
udviklermaskinen under hændelsen, så det er ikke udpeget som årsag, og det bør ikke antages.
