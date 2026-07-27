---
title: P2-31 — statisk typecheck som gate, med analytics-service som pilot
date: 2026-07-27
status: open
backlog-items: [P2-31]
related:
  - ../findings/2026-07-27-sync-trigger-double-value.md
  - ../findings/2026-07-25-per-worker-image-staleness.md
---

# P2-31 — statisk typecheck som gate

## Goal

Få mypy til at køre som en **blokerende** gate på mindst én service, og gøre det på en måde
hvor rulle-ud til resten er at tilføje et servicenavn til en liste. Done når: (a) `make -C
services/analytics-service typecheck` exit-koder 0 på master, (b) samme kommando exit-koder
≠0 hvis `SyncTrigger`-klassen af fejl genindføres, og (c) CLAUDE.md's mypy-afsnit ikke længere
er mærket ASPIRATIONAL for de services der er med.

Acceptkriteriet er bevidst **ikke** "typecheck exit-koder 0". Det ville en tom check også
gøre. Se [Verification](#verification).

## Context

[Dobbelt `.value` på sync-claimet](../findings/2026-07-27-sync-trigger-double-value.md): en
`str` mod en port der erklærer `SyncTrigger` brød hver eneste bank-sync i to dage, og ingen
gate blinkede. Fundet listede tre lag tavshed; dette er det generelle af dem.

Målt i dag, 2026-07-27, og det er tal planen hviler på:

**1. Default-mypy fanger fejlen. `--strict` er ikke nødvendigt.** Jeg kopierede
banking-service til scratch, genindførte de tre `trigger.value`-kaldsteder og kørte mypy 1.11
uden strictness-flag:

```
app/application/service.py:274: error: Argument 5 to "try_claim_sync" of
  "IBankConnectionRepository" has incompatible type "str"; expected "SyncTrigger"  [arg-type]
app/application/service.py:294: error: (samme)
app/application/service.py:309: error: (samme, steal_sync_claim)
```

Alle tre. Backloggens formulering ("start med `--strict` slået fra") er altså ikke et
kompromis her — default-niveauet er nok til netop denne fejlklasse, fordi annotationerne
allerede findes.

**2. Men kun hvis shared-pakkerne kan resolves — ellers er checken grøn på bugen.** Samme
buggy kopi, samme mypy, uden `MYPYPATH` mod `services/shared/*`: **5 fejl, ingen af dem
arg-type.** `SyncTrigger` degraderer til `Any` og de tre kaldsteder er lovlige. Med
shared på path: 16 fejl, inklusive de tre. Det er den samme fejlmode som P3-40's:
*en gate der kører og intet finder ser ud som en gate der virker.*

**3. To af fire shared-pakker mangler `py.typed`.** `contracts` og `auth` har markøren;
`domain` og `messaging` har den ikke og har den ikke i git. Konsekvens målt på
analytics-service med deps installeret og dens egen (allerede strenge) config:

```
app/domain/budget_period.py:11: error: Skipping analyzing "domain": module is installed,
  but missing library stubs or py.typed marker  [import-untyped]
Found 1 error in 1 file (checked 41 source files)
```

Én fejl i hele servicen, og den fejl *er* py.typed-hullet. Alt fra `shared/domain` og
`shared/messaging` er `Any` i alle 12 services i dag. Det er 2 tomme filer at rette.

**4. Baseline per service** (mypy 1.11, `--ignore-missing-imports`, shared på `MYPYPATH`,
deps **ikke** installeret — så tallene er nedre grænser, og de er ikke sammenlignelige på
tværs, fordi kun analytics har en `[tool.mypy]`-blok mypy selv læser):

| Service | Fejl | Noter |
|---|---|---|
| ai-service | 0 | måling hul: fastapi/pydantic/ollama alle uresolvede |
| user-service | 4 | |
| analytics-service | 1 | **med deps + streng config: 1**, og det er py.typed-hullet |
| goal-service | 1 | fejlen er `Source file found twice` — en path-config-fejl, ikke en typefejl |
| notification-service | 5 | |
| budget-service | 11 | |
| saga-service | 11 | |
| transaction-service | 12 | |
| account-service | 12 | ingen pyproject → P3-39/P3-23 først |
| banking-service | 13 | ingen pyproject → P3-39/P3-23 først |
| categorization-service | 17 | |
| gateway-service | 98 | outlier, Strawberry-genereret; eget item |

## Beslutninger denne plan træffer

**Checker: mypy, ikke pyright.** Begrundelse: `analytics-service` har allerede både
`[tool.mypy]` og mypy i sin dev-group, så piloten bliver "kald det der står", ikke "opfind en
config"; CLAUDE.md navngiver mypy; og mypy installeres af `uv sync --dev` i servicens eget
låste venv, hvor pyright ville kræve Node i tolv i dag rent-Python CI-jobs *og* stadig skulle
peges på det samme venv. Omkostning vi accepterer: mypy er langsommere end pyright, og vi
opgiver en checker der er bedre til inferens i uannoteret kode — hvilket ikke er vores problem,
da annotationerne findes.

**Rodens `pyrightconfig.json` slettes.** Tre linjer `extraPaths` der dækker 2 af 14
services, som intet invokerer. Den er grunden til at "kører vi typecheck?" var et tvetydigt
spørgsmål i to dage. Enten er den en gate (det er den ikke) eller den er IDE-hjælp der lyver
om pathene (det er den). Væk.

**Pilot: analytics-service.** 1 målt fejl med deps og streng config, konfigurationen findes
allerede, og den er ikke på nogen kritisk fejl-sti under udrulningen.

**Piloten dækker ikke den service hvor bugen var.** banking- og account-service mangler
pyproject (P3-23/P3-39), og CI's fallback-gren for dem er `pip install -r requirements.txt`
uden dev/runtime-split — der er ikke noget sted at hænge mypy op. Det skal siges rent frem
for at blive opdaget senere: **P2-31 beskytter ikke banking mod den fejl der motiverede
P2-31**, før P3-23 er lukket. Derfor står banking eksplicit i udrulningsrækkefølgen med sin
blocker, og derfor er kontrol-testen i trin 5 formuleret som "fejlklassen", ikke "denne fil".

**Gate-form: hård, per-service allowlist.** Ét `typecheck`-target per service + ét CI-step i
den eksisterende `python-services`-matrix, der kun kører for services på en eksplicit liste.
Ikke `continue-on-error`, ikke en baseline-fil med accepterede fejl. En blød gate er præcis
den fejlmode dette item findes for at rette.

## Non-goals

- **Ingen adfærdsændring nogen steder.** Kun `py.typed`-markører, Makefile-targets, CI-steps,
  config og — hvor en fejl viser sig at være reel — typeannotationer. En typefejl der kræver
  *runtime*-ændring for at rette, rettes ikke her: den bliver et finding og en `# type: ignore`
  med issue-reference, så den ikke gemmes væk som en annotation.
- **Ikke `--strict`.** Ingen `disallow_any_*`, ingen `strict_equality`. Målingen viser at
  default-niveauet fanger fejlklassen; strictness kan skærpes per service bagefter.
- **Ikke gateway-service.** 98 fejl, næsten alle fra Strawberry-genereret kode; det er et
  selvstændigt stykke arbejde, ikke en pilot-udvidelse.
- **Ikke P3-41** (bare mocks → `spec=`). Fundet siger det eksplicit: `spec=` fanger forkerte
  metode*navne*, ikke forkerte argument*typer*, så den ville ikke have fanget denne fejl.
  Rækkefølgen er P2-31 først; ellers lukkes det forkerte hul med en følelse af at være færdig.
- **Ikke frontend/TypeScript.**

## Steps

1. [ ] **`py.typed` på `shared/domain` og `shared/messaging`.** To tomme filer
   (`domain/domain/py.typed`, `messaging/messaging/py.typed`) + `[tool.hatch.build]`
   force-include hvis wheelen ikke tager dem med af sig selv (verificér — `packages = ["domain"]`
   bør, men det er et af de steder hvor "bør" har kostet os to dage før).
   Bevis: analytics' `uv run mypy` går fra 1 fejl til 0.
   *Commit 1.* Dette trin har værdi alene, uafhængigt af resten af planen: uden det er alle
   contracts-typer `Any` i hver service, også i IDE'en.
2. [ ] **`typecheck`-target i analytics' Makefile** — `uv run mypy` (configen ligger i
   pyproject), plus linjen i `help`. Ret samtidig `[tool.mypy]` så den er eksplicit om
   `mypy_path` for shared, i stedet for at arve CI's `PYTHONPATH` ved held.
   *Commit 2.*
3. [ ] **Slet `pyrightconfig.json`** i roden. *Commit 2* (samme logiske enhed: der er én
   checker nu).
4. [ ] **CI-step.** I `python-services`-jobbet, efter `Ruff format check`:
   et `Typecheck (mypy)`-step der kører `uv run mypy` når `${{ matrix.service }}` er på
   allowlisten, og printer et `::notice` "typecheck not enabled for <svc> (P2-31)" ellers.
   Allowlisten starter med `analytics-service` alene. Hvorfor et notice og ikke et tavst skip:
   P3-40 lærte os at et step der skippes ser identisk ud med et step der lykkes.
   *Commit 3.*
5. [ ] **Kontrol — bevis at gaten fanger fejlklassen, ikke bare at den er grøn.** Se
   [Verification](#verification). Dette trin producerer ingen commit på master.
6. [ ] **Udrulning, i målt rækkefølge, én commit per service**: user (4) → notification (5) →
   goal (1 + path-config-fejlen) → ai (0, men mål igen med deps installeret først) →
   budget (11) → saga (11) → transaction (12) → categorization (17). Hver service:
   `mypy` i dev-group, `[tool.mypy]`-blok kopieret fra analytics, `typecheck`-target,
   navn på CI-allowlisten. Blokeret indtil P3-23/P3-39: **banking, account**. Eget item:
   **gateway**.
   Dette trin skal ikke afsluttes i én session; gaten er allerede reel efter trin 4.
7. [ ] **CLAUDE.md.** Erstat ASPIRATIONAL-noten med hvad der er sandt: hvilke services
   gaten dækker, at niveauet er default-mypy og ikke `--strict`, og at banking/account er
   udenfor med henvisning til P3-23. Samme sted: en linje om at
   `py.typed` er obligatorisk på nye shared-pakker.
   *Commit sidst i hver bølge, så noten aldrig overdriver dækningen.*

## Verification

Fejlmoden for *dette item* er en gate der kører og intet fanger. Så beviset er en **kontrol**,
ikke kun en treatment — lektien fra P3-40.

1. **Treatment (skal være grøn):** `make -C services/analytics-service typecheck` → exit 0,
   `Success: no issues found in 41 source files`.
2. **Kontrol A — fejlklassen, i piloten (skal være rød):** indfør midlertidigt et
   arg-type-brud mod en af analytics' egne ports (fx send en `str` hvor en enum er erklæret),
   kør targetet, bekræft `[arg-type]` og exit ≠0, revertér. Hvis kontrollen er grøn, er
   configen hul og trin 2 er ikke færdigt.
3. **Kontrol B — den rigtige fejl, uden for gaten:** banking-scratch-kopien fra i dag
   (bug genindført) skal give de tre `[arg-type]`-fejl når mypy køres med shared på path.
   Kørt og bekræftet — teksten står i [Context](#context). Det er beviset for at gaten
   *ville* have fanget produktionsfejlen, og det er det nærmeste vi kommer, indtil P3-23
   gør banking gate-bar.
4. **Kontrol C — at CI-steppet faktisk kørte:** åbn run-loggen for det pushede commit og
   verificér at `Typecheck (mypy)` har output for `analytics-service` og notice-linjen for de
   elleve andre. Et grønt *run* er også grønt hvis steppet blev skippet.
5. **Ingen regression:** `make -C services/analytics-service test` og `make ci-status` grøn
   for branchen.
6. **Aldrig** pipe et af ovenstående gennem `tail`/`head` før et `&& git commit` — exit-koden
   bliver pipens sidste led. Sket 2×.

## Risks & rollback

- **`py.typed` afslører fejl i hver service på én gang.** Sandsynligt: alle contracts-typer
  bliver skarpe samtidig, og trin 1's tal (analytics: 1 → 0) siger intet om de elleve andre,
  som ikke har nogen gate der kan blive rød. Det er *hele pointen*, men det betyder at
  baseline-tallene i Context kan stige mærkbart når hver service faktisk måles med deps.
  Håndtering: trin 6 måler per service **før** den sættes på allowlisten, og en service med
  uventet mange fejl bliver et selvstændigt item i stedet for at trække bølgen.
  Rollback: `py.typed` kan ikke rulles tilbage uden at gøre alle typer `Any` igen — men den
  kan ikke bryde runtime, kun gøre en check rød.
- **Målingerne er nedre grænser.** Elleve af tolv tal er målt uden deps, hvor
  fastapi/pydantic/elasticsearch er `Any`. ai-services 0 er derfor ikke troværdig.
  Håndtering: står i tabellen; trin 6 gen-måler.
- **`disallow_untyped_defs` i analytics' config er strengere end resten af repoet.** Hvis den
  viser sig at koste mere end den fanger under udrulningen, er det billigere at slække
  *analytics* til repo-niveau end at hæve elleve services. Beslut ved første service der
  rammer det, ikke nu.
- **Rollback for gaten:** ét servicenavn ud af CI-allowlisten. Det er derfor formen er en
  liste og ikke tolv kopierede steps.
