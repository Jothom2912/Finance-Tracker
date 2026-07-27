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
tværs, fordi kun analytics har en `[tool.mypy]`-blok mypy selv læser).

> **Korrektion 2026-07-27, efter trin 1.** Tallene nedenfor er ca. det halve af virkeligheden,
> ikke "en smule lave". Målt gennem servicens eget venv med deps installeret er
> **transaction-service 27 fejl, ikke 12** (28 efter `py.typed`). Værre: da jeg gen-målte
> tabellen efter trin 1 fik jeg *identiske* tal og læste det først som "py.typed havde ingen
> effekt" — men opsætningen var blind for spørgsmålet, fordi `MYPYPATH` mod kildekoden får
> mypy til at analysere `domain` som source uanset markøren. En måling der ikke kan skifte
> værdi er ikke en måling. Trin 6 skal måle per service gennem `uv run`, ikke `uvx` + `MYPYPATH`.

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

1. [x] **`py.typed` på `shared/domain` og `shared/messaging`** — gjort 2026-07-27,
   `67c29dcc` + `617bbc11`. Ingen `force-include` nødvendig: begge wheels blev bygget og
   indholdet listet, `packages = ["domain"]` tager filen med, som i contracts.
   Bevis: analytics' `uv run mypy` gik fra `1 error` til
   `Success: no issues found in 41 source files`. 123 tests grønne.
   **Deviation (godkendt undervejs): versionsbump til 0.1.1 + re-lock af 11 `uv.lock`.**
   Markøren nåede ikke ud af sig selv — path-deps installeres som kopier, ikke editable, og
   uv genopretter dem ikke ved uændret version. Målt: `uv sync --dev` i user-service sagde
   "Audited" og beholdt `messaging 0.1.0` uden markør, så `make typecheck` lokalt og i CI
   kunne give forskellige svar. Kontrol efter bumpet: samme urørte venv gik til
   0.1.1-med-markør på et almindeligt `uv sync --dev`. Diffen er udelukkende versionslinjen;
   664 tests grønne på tværs af de 9 dependents.
2. [x] **`typecheck`-target i analytics' Makefile** — gjort, `4b09ecd7`. `uv run mypy`, med i
   `check`, linje i `help`.
   **Deviation: ingen `mypy_path`.** Planen sagde at gøre den eksplicit; det er nu forkert.
   Efter trin 1 resolves shared som *installerede* pakker via `py.typed`, og at pege mypy på
   kildekoden oveni er netop det der producerer goal-services `Source file found twice under
   different module names`. Venv'et er eneste sandhedskilde. Begrundelsen står som kommentar
   i Makefilen, så den ikke bliver "rettet" tilbage.
   **Fangst undervejs: gaten kører mypy 2.1.0, ikke 1.11.0.** Alle baseline-tal i Context er
   fra 1.11 via `uvx`; analytics' `uv.lock` pinner 2.1.0. Kontrol B er derfor kørt om under
   2.1.0 — alle tre `SyncTrigger`-kaldsteder flagges også dér. Uden det tjek ville "beviset"
   have handlet om en anden checker end den der kører.
3. [x] **Slet `pyrightconfig.json`** — gjort, `4b09ecd7`. Kun notes refererede den;
   `architecture/infrastructure.md`s påstand om pyright-dækning rettet i samme commit.
4. [x] **CI-step** — gjort, `de39bb6f`. `Typecheck (mypy)` mellem `Ruff format check` og
   `Bandit`, allowlisten `TYPECHECK_SERVICES: "analytics-service"`, shell-betingelse frem for
   `if:` (et `if:`-skippet step vises som "skipped" og kan ikke skelnes fra "fine").
   Verificeret bredere end det ene tilfælde: matchlogikken kørt mod alle 12 servicenavne,
   delstreng-fælder (`analytics`, `analytics-service-x`, `xanalytics-service`) afvist korrekt,
   to-navns-liste gater begge, begge grene af step-kroppen kørt.
   **Note til kontrol C:** steppet kører for *alle* 12 services (betingelsen er indeni), så
   step-conclusion kan ikke bruges som bevis. Den verificerbare asymmetri er
   annotationerne: de 11 ikke-gatede skal have et `::notice`, og `analytics-service` skal
   **ikke** have et. Mangler noticen for de 11, er betingelsen forkert; findes den for
   analytics, gater den ikke.

   **Ekstra, uden for planen: `shared/domain` havde ingen CI** (`9dec9338`). Matrixen dækkede
   3 af 4 shared-pakker. Hullet var usynligt fordi en naiv tilføjelse ville have *fejlet*:
   `domain` brugte den gamle `[project.optional-dependencies] dev`, så `uv sync --dev`
   afinstallerede pytest og `uv run pytest` døde med `Failed to spawn`. Konverteret til
   `[dependency-groups]`; dep-gruppe-skiftet forældede analytics/gateway/budgets locks, som
   er re-locket. 42 tests kører nu i CI, run 19/19 grøn.
5. [x] **Kontrol — bevis at gaten fanger fejlklassen, ikke bare at den er grøn.** Se
   [Verification](#verification). Dette trin producerer ingen commit på master.
   Alle fire kontroller kørt. Kontrol C afsluttet 2026-07-27 mod run #239 på `c55342b0`,
   hvor allowlisten er to services: **10 ikke-gatede med `::notice`, 0 for analytics og
   user.** Begge retninger. Step-conclusion var `success` for alle 12 — som forudset
   beviser den ingenting, og det var annotationerne der bar dommen.
   **Måleren fejlede først, gaten gjorde ikke.** Første kørsel meldte RØD fordi
   navne-parseren ledte efter `job (navn)`, mens CI navngiver jobs `navn - Python 3.11`;
   begge gatede services blev talt som ikke-gatede-uden-notice. Rådata var korrekte og
   *så* korrekte ud, hvilket er fælden: at læse tabellen med øjnene og kalde det grønt
   ville have flyttet dommen fra maskinen til mig og efterladt måleren i stykker.
   Parseren har nu en hård exit hvis et jobnavn ikke kan udledes til `*-service` — en
   blind parser skal sige fra, ikke gætte. Slægtning til trin 1's korrektion: dér kunne
   målingen ikke skifte værdi, her målte den det forkerte navn.
6. [ ] **Udrulning, i målt rækkefølge, én commit per service.**
   - [x] **user-service** — `b63962ca`. Ærlig måling gennem `uv run`: 4 fejl, og *samme 4*
     med og uden `disallow_untyped_defs`, så analytics' config kunne bruges uslækket.
     Tre af de fire havde rigtige fix, ikke ignores: pydantics mypy-plugin løste de to
     `Settings()`-`call-arg`, og `types-python-jose` løste stub-fejlen. Den fjerde er
     [en usand outbox-port](../findings/2026-07-27-outbox-port-declares-foreign-entity.md)
     → P2-32, behandlet med begrundet `# type: ignore[assignment]` + `warn_unused_ignores`,
     så den selv fejler når fixet lander. Kontrolleret begge veje; 48 tests grønne.
     **Pointe værd at bære videre:** gaten fandt en falsk portkontrakt på sin første nye
     service, inden for en time. Det er items egen begrundelse, leveret igen.
   - Resterende, i målt rækkefølge: notification (5) →
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
4. **Kontrol C — at CI-steppet faktisk gatede, og kun der hvor det skal:** steppet kører for
   alle 12 services (betingelsen ligger i shell-kroppen), så en grøn step-conclusion beviser
   intet. Verificér i stedet asymmetrien i run-annotationerne: `::notice` for hver
   ikke-gatet service, og **intet** notice for dem på allowlisten. Begge retninger skal
   holde — mangler noticen bredt, er betingelsen forkert; findes den for en gatet service,
   gater gaten ingenting.
   **Kørt og grøn 2026-07-27** (run #239, `c55342b0`): 10 med notice, 2 uden, allowliste
   `analytics-service user-service`. Gentages ved hver ny service på allowlisten — det er
   samme kontrol, med to tal der skal flytte sig i hver sin retning.
   Praktisk: annotationerne hentes per job via `/repos/{slug}/check-runs/{job_id}/annotations`
   på det anonyme API (~14 kald per kørsel, loft 60/t). **Sæt `GH_TOKEN`** hvis kontrollen
   skal køres mere end fire gange i timen; `scripts/ci_status.py` læser samme variabel.
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
