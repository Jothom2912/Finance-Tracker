---
title: Et CI-job kan hænge i seks timer uden at nogen får det at vide — én manglende grænse, ikke to
date: 2026-07-28
severity: MEDIUM
status: resolved
resolved-by: P2-38 (2026-07-29) — `timeout-minutes` på alle 5 job-definitioner efter målt baseline, verificeret rød med `sleep 120` mod en grænse på 1 min (run 30405860162). **To af fundets egne påstande var forkerte og er rettet i teksten:** `timeout-minutes` havde 1 hit ikke 0, og ES-fixturen manglede ikke en wait-timeout — testcontainers 4.14.2 bounder den til 120 s, hvorfor de 836 s beviser at hængen lå i det ubundne image-pull. Der var altså **én** manglende grænse, ikke to. Image-cachen er stadig ikke lavet.
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

> **Rettelse 2026-07-29 (P2-38).** Begge punkter herunder var faktuelt forkerte, målt under
> implementeringen. De står uændret for sporbarhed; læs rettelsen efter dem.

Fejlen er ikke flaken. Flaken er uundgåelig. Fejlen er at **intet oversætter den til et
signal**:

1. **`services/analytics-service/tests/integration/conftest.py:19-24`** — den session-scopede
   `es_container`-fixture gør `with container:` på en `ElasticSearchContainer` uden nogen
   wait-timeout. testcontainers venter så på ES' readiness uden en øvre grænse.
2. **`.github/workflows/ci.yml`** — `grep -n "timeout-minutes"` giver **0 hits** i hele filen,
   så alle jobs arver GitHub Actions' default på **360 minutter**.

I serie betyder de to at en forbigående ES-fejl bliver en tavs flere-timers hæng frem for en
rød kørsel.

### Rettelse: der var én manglende grænse, ikke to — og hængen lå et tredje sted

**Punkt 2 var talt forkert.** `grep -c timeout-minutes .github/workflows/ci.yml` gav **1**, ikke
0: P2-39 havde sat `timeout-minutes: 30` på `e2e-tests`. Det var 4 af 5 job-definitioner der
manglede en grænse.

**Punkt 1 var forkert i substansen.** `testcontainers` 4.14.2 sætter selv
`WaitStrategy._startup_timeout = testcontainers_config.timeout`, altså `TC_MAX_TRIES` (120) ×
`TC_POOLING_INTERVAL` (1) = **120 s**, og `HttpWaitStrategy` rejser ved overskridelse en
usædvanlig informativ `TimeoutError` med endpoint, metode, forventede statuskoder og et hint.
Verificeret ved at pege fixturen på en container der starter men aldrig lytter på 9200: den
fejlede læsbart efter 13,8 s med grænsen sat til 10 s. Waiten var altså aldrig ubundet, og
acceptkriteriet "fejler med en læsbar pytest-fejl" var opfyldt af pakke-defaults.

**Og dermed lå hængen ikke i waiten — de 836 s beviser det.** Var den i wait-strategien, var
jobbet fejlet efter 120 s. At det sad 836 s viser at hængen lå i `docker_client.run(...)`'s
image-**pull**, som kaldes *før* wait-strategien og er ubundet; 4.14.2 eksponerer ingen knap for
den, og det samme gælder Ryuk-containeren.

**Konsekvens for fix-retningen nedenfor:** "begge grænser, den ene uden den anden flytter kun
symptomet" holder ikke. Der findes kun **én** grænse der kan fange denne klasse, og det er den
ydre — `timeout-minutes` på jobbet. Fixturens grænse er skrevet eksplicit som en *pin* mod at
defaulten eller de to env-vars flytter sig, ikke fordi den manglede. Til gengæld gør udpegningen
af pull-stien den foreslåede **image-cache mere relevant**, ikke mindre.

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

*(Skrevet før implementeringen. Se rettelsen ovenfor for hvad der faktisk holdt.)*

Begge grænser, fordi den ene uden den anden kun flytter symptomet:

- `timeout-minutes` på jobbene i `ci.yml`. Sæt den ud fra målt varighed med rigelig margin
  (analytics-jobbet er ~1–2 min i dag), ikke ud fra et rundt tal. Effekten er at en hæng bliver
  **rød med en læsbar log** i stedet for usynlig.
- En eksplicit wait/startup-timeout på `es_container`. Den giver en fejlbesked der peger på ES
  frem for en pytest der bare tier — altså forskellen mellem "ES kom ikke op" og ingenting.

Overvej samtidig om `docker.elastic.co`-imaget skal caches i CI; registryet svarede fint fra
udviklermaskinen under hændelsen, så det er ikke udpeget som årsag, og det bør ikke antages.

## Leveret (P2-38, 2026-07-29)

`timeout-minutes` på alle 5 job-definitioner, sat efter baseline målt over 10 grønne kørsler:
`repo-lint` 5 (max 13 s), `python-services` 8 (max 120 s), `shared-packages` 5 (max 20 s),
`frontend` 5 (max 56 s). Grænsen er ~3× målt max med et gulv på 5 min, fordi 3× max på de tre
billige jobs ville være 40–170 s og gøre dem røde på en langsom `setup-python` frem for på en
hængning.

**Verificeret rød**, ikke kun sat: `repo-lint` med `timeout-minutes: 1` + `sleep 120` på en
throwaway-branch blev afbrudt efter 72 s (run 30405860162).

**Det uafklarede punkt fundet blev skrevet om — "ingen alarm på varighed" — er stadig sandt.**
Grænsen konverterer 360 min til 5–8 min, men den siger ikke *hvorfor*: GitHub rapporterer en
timeout som `cancelled`, ikke `failure`, og loggens eneste spor er
`##[error]The operation was canceled.` Ordet *timeout* optræder ikke, grænsen navngives ikke, og
`gh run view --log-failed` returnerer tomt med rc=1 fordi der ikke er noget fejlet job. Signalet
er "job `cancelled` + varighed ≈ grænsen". Det er derfor den målte baseline står i en kommentar
ved hver grænse — den er det der gør et afbrudt job læseligt som timeout frem for som "nogen
trykkede annuller".

Image-cachen er **ikke** lavet, og den er nu bedre begrundet end da fundet blev skrevet, fordi
pull-stien er udpeget som der hvor de 836 s lå.
