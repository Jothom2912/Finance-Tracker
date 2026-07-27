---
title: P2-31 — statisk typecheck som gate, med analytics-service som pilot
date: 2026-07-27
status: done
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
   - [x] **notification-service** — `0295ab98`. Målt gennem `uv run`: **7 fejl, ikke
     tabellens 5**. Fire rettet uden adfærdsændring: to `__aexit__` uden annotationer,
     tre `Result[Any].rowcount` (samlet i én `_rowcount()`-helper — `execute()` er typet
     `Result`, men returnerer `CursorResult` for DML), og `Settings()`-`call-arg`.
     Den femte er
     [INTERNAL_API_KEY](../findings/2026-07-27-internal-api-key-optional-but-mandatory.md)
     → P2-33: samme løgn i 6 services, samme fejl venter i banking (2 kaldsteder) og goal,
     så begrundet `# type: ignore` frem for en drive-by. Kontrolleret begge veje;
     90 tests grønne.
     **`disallow_untyped_defs` kostede to `__aexit__`-signaturer** — planens åbne spørgsmål
     om at slække analytics' config er dermed besvaret med nej, ved den første service der
     rammer det.
     **Fangst med tilbagevirkende kraft: `pydantic.mypy` uden `init_typed` er værre end
     intet plugin** (`f7fc0e9f`). Default-pluginet syntetiserer et `__init__` hvor alle
     felter er `Any`; pydantic v2 bruger `dataclass_transform`, så mypy typer allerede
     model-konstruktion nativt. Pluginet *erstattede* altså den native check med `Any` i
     hele user-service fra `b63962ca` til nu. Sporet var to `type: ignore` i notifications
     `dto.py` som pluginet afmeldte, og `warn_unused_ignores` fangede. Rettet begge steder
     med `[tool.pydantic-mypy] init_typed = true`; user-service er stadig `Success`, så
     regressionen var i dækningen, ikke i koden. **Alle senere services skal have
     `init_typed` hvis de får pluginet.**
     **Versionsdrift noteret:** notification låser mypy 2.3.0, analytics 2.1.0. Ikke et
     problem i dag, men gaten er ikke den samme checker på tværs af services.
   - [ ] **goal-service — trukket ud af bølgen, se
     [P2-34](../findings/2026-07-27-goal-entity-two-runtime-types.md).** Målt til **23 fejl,
     ikke tabellens 1** (og 1-tallet var selv målefejlen). 15 mekaniske, 3 kendte
     (P2-32 ×2, P2-33), men fem ægte, hvoraf fire sidder på samme problem: `Goal` bygges med
     `float` af det ene repository og `Decimal` af det andet, `models.py` erklærer
     `Mapped[float]` på en `Numeric`-kolonne, og forskellen når ud i event-payloads via
     `str()` som `"100.0"` mod `"100.00"`. Dertil `Goal.status: str | None` hvor `GoalStatus`
     findes. Risiko-klausulen nedenfor er anvendt bevidst: at lukke fire ignores på ét
     pengetypnings-problem ville gøre `ignore` til normalen i stedet for undtagelsen.
   - [x] **ai-service** — `508c20ab`. Tabellens 0 var hul (fastapi/pydantic/ollama
     uresolvede); ærlig måling gav **3**. Settings() løst med pluginet + `init_typed`,
     en manglende returtype på `event_generator`, og `_call() -> str` hvor ollama typer
     `message.content` som optional. Sidstnævnte er allerede håndteret i koden — `None`
     fejler `model_validate_json` som `ValidationError` og tager fallbacket — så
     annotationen var det eneste forkerte og blev gjort sand uden adfærdsændring.
     Kontrolleret at gaten bider: en `int` mod `chat(model: str)` flagges, og mypy
     resolver ollamas egne typer. 91 tests grønne.
     **Note til resten af bølgen:** `check: lint format-check ## kommentar` har sine
     prerequisites *før* `##`. Et `typecheck` tilføjet efter kommentaren ser rigtigt ud i
     diffen og kører aldrig. Verificér med `make -n check`, ikke ved at læse Makefilen.
   - [x] **budget-service** — `PENDING`. Målt gennem `uv run`: **26 fejl, ikke tabellens
     11**. To af dem var ikke typefejl men en **manglende afhængighed**: servicen importerer
     `contracts.*` men erklærede ikke `finans-tracker-contracts` (7 andre services gør), og
     kompenserede med `PYTHONPATH=../../shared/contracts` i tre Makefile-targets. Docker
     skjulte det, fordi imaget `pip install`er `/shared/contracts` direkte. Fixet er
     deklarationen, ikke `ignore_missing_imports` — sidstnævnte er præcis Context-målingens
     fejlmode, hvor `Any` gør gaten grøn på bugen. `PYTHONPATH`-hackene er væk med samme
     begrundelse som trin 2's: kildetræ til tests + installeret kopi til mypy er to
     sandhedskilder for én pakke.
     Af de resterende 24 var 21 mekaniske: 13 returtyper (routes + `lifespan`),
     `types-python-jose`, 3× `Result[Any].rowcount` (samme `rowcount()`-helper som
     notification, nu i `adapters/outbound/sql_result.py`), og 3× `dto: X = ...` — en
     `EllipsisType`-default der kun fandtes for at komme efter `Query(...)`; `dto` er flyttet
     først i signaturen, hvilket FastAPI behandler identisk.
     P2-32 igen (**omfanget i fundet bekræftet: 7 services, budget er nr. 2**), og de sidste
     tre er
     [Optional id](../findings/2026-07-27-optional-id-hides-unpersisted-entity.md) → **P2-35**,
     behandlet med begrundede ignores. Kontrolleret begge veje — og kontrollen dækkede
     bevidst *også* et forkert felt i en `contracts`-event, for at bevise at den nye
     deklaration gør de typer skarpe og ikke blot tavse. 117 tests grønne (61+56).
     **Ny vane værd at bære videre:** da fundet påstod noget om SQL (`== None` →
     `IS NULL` → 0 rækker → 409), compilede jeg statement'et frem for at tro på det. En
     fejlsti man kun har ræsonneret sig til er samme slags påstand som en uverificeret
     portdocstring — jf. sync-trigger-fundet.
   - [x] **saga-service** — `PENDING`. **Første service hvor den ærlige måling gav *færre*
     fejl end tabellen: 2, ikke 11.** Servicen er allerede annoteret; tabellens 11 var
     import-støj som deps opløser. Fordi retningen var uventet, blev
     `disallow_untyped_defs` probet med en uannoteret funktion frem for antaget aktiv —
     og **den første probe var selv blind**: `str.replace` på en anchor der ikke fandtes er
     en tavs no-op, så "ingen ny fejl" betød "ingen ny kode". Tredje gentagelse af trin 1's
     lektie, nu på verifikationsværktøjet i stedet for på målingen.
     De 2 fejl var begge reelle:
     - `outbox_adapter.py:52` → [SerializableEvent krævede settable
       attributter](../findings/2026-07-27-serializable-event-demands-mutable-attrs.md).
       Rettet i shared (`messaging` 0.1.2), egen commit før denne. **Kun saga kunne se det**:
       budget og user kalder gennem egen port, hvor P2-32-ignoren står, og
       `# type: ignore[assignment]` slår typen fast for alle senere kald på navnet — én
       begrundet ignore skjulte en anden, urelateret usand kontrakt.
     - `main.py:51` → `int((instance.context or {}).get("user_id"))` på en ejerskabs-check.
       `int(None)` var *tilsigtet* fanget af `except TypeError`, så None-grenen er nu skrevet
       ud. Grenen var **utestet** (den eksisterende 403-test dækker kun forkert bruger, ikke
       manglende `user_id`), så fire shapes er pinnet — og de nye tests er kørt mod den
       **gamle** kode først: 9/9 grønne der også, hvilket er beviset for at ændringen er
       adfærdsneutral frem for påstanden om det.
     Kontrolleret begge veje, og efter en løsnet Protocol specifikt at den ikke blev *tom*:
     `correlation_id: int | None` mod `str | None` flagges stadig. Mutability- og
     optionality-aksen blev løsnet, typeaksen ikke. 54 tests grønne (50 + 4 nye).
   - [x] **transaction-service** — `PENDING`. 26 fejl, som gen-målingen i trin 1 forudsagde
     (27). Men **26 fejl var 6 rødder**, og den nyttige lektie er at fejltællinger ikke
     rangerer arbejde: 20 af de 26 var én rod, og den rod var den vigtigste ting i hele
     bølgen indtil nu.
     - **`x-retry-count` læses fem steder på fire måder** →
       [finding](../findings/2026-07-27-retry-header-read-five-ways.md) → **P2-36**. De to
       saga-consumere (transaction + banking, kopi-pastet) special-caser `bytes` og
       sammenligner så den rå header med en int: `'3' >= 3` er `TypeError`. Og fordi
       læsningen står **inde i** `except Exception`, ackes beskeden hverken eller
       republishes → uendelig redelivery uden at tælleren rykker. Rettet i transaction med
       én testet helper; de øvrige fire steder er P2-36. Bevidst adfærdsdelta, dokumenteret.
     - **`categorization_client: object | None`** — application-laget afhang af `object`,
       altså af ingenting, hvilket er dårligere end både en port og en konkret adapter.
       Erstattet af `ICategorizationClient` + `CategorizationOutcome` som Protocols i
       ports-modulet. **To lektioner fra tidligere i samme session anvendt med det samme:**
       read-only properties (`CategorizationResult` er også `frozen=True`, så plain
       attributter ville have fejlet præcis som `SerializableEvent`), og `Sequence` frem for
       `list` på returtypen — `list[CategorizationResult | None]` er ikke en
       `list[CategorizationOutcome | None]`, fordi `list` er invariant. Den nye port fangede
       mismatchet i `dependencies.py` med det samme.
     - **`add_batch(entries: list[...])`** → `Sequence`, samme invarians-årsag.
     - **P2-32 i en tredje form**: `class TransactionOutboxAdapter(OutboxRepository,
       IOutboxRepository)` — base-class-konflikt frem for tilskrivning. Begrundet ignore.
       **Tredje service af 7; omfanget i P2-32 er nu bekræftet tre gange.**
     - `external_id`-narrowing gennem en list comprehension: filtret flyttet ind i den
       comprehension der har brug for det.
     Kontrol: en `str` mod porten og en felt-typo begge fanget — hvor `object | None`
     tidligere gjorde typo'en umulig at skelne. 263 tests grønne (247 + 16 nye).
   - [x] **categorization-service** — `PENDING`. **Sidste service i bølgen.** Målt gennem
     `uv run`: 20 fejl, ikke tabellens 17 — men **20 fejl var 8 rødder**, og fordelingen er
     omvendt af transactions: dér var den største klynge det vigtigste fund, her er den
     kendt gæld, og de små rødder bar indholdet.
     - **9 af de 20 er P2-35** (`id: Optional[int]`). Categorization er den største af
       fundets fire services (6 entiteter). Gated med begrundede ignores frem for trukket
       ud som goal-service, fordi kriteriet i fundet aldrig var *antallet*: alle 9 er
       repo-hentede entiteter, ingen målt divergens i data der forlader servicen. Roden
       forklares én gang i modulets docstring frem for 9 gange inline; `warn_unused_ignores`
       gør hver linje selvfejlende når P2-35 lander, uanset kommentarteksten.
     - **`_to_dto(category: object)`** — transaction-services `object | None`-lektion i sin
       anden service, nu på en mapper. `.type`, `.id`, `.name` var alle ukontrollerede.
       Annoteret `Category`, og `hasattr(category.type, "value") else str(...)`-grenen
       fjernet: der findes **præcis ét sted** i servicen der bygger en `Category`
       (`postgres_category_repository._to_entity`), og det coercer altid med
       `CategoryType(...)`. Grenen var altså død *ved konstruktion*, ikke sandsynligvis død
       — verificeret med grep frem for antaget. To søsterforekomster i `CategoryUpdatedEvent`
       / `CategoryDeletedEvent` fjernet på samme bevis; at rette én af tre ville have
       efterladt en kommentar der modsiger koden ved siden af.
     - **Narrowing dør i en lambda.** `if self._ml is not None` narrower ikke ind i
       `lambda: self._ml.predict(...)`, fordi lambdaen fanger `self` og kaldes senere inde i
       `_try_tier`. Ikke hypotetisk: en `AttributeError` dér ville blive slugt af
       `except Exception` og logget som "tier failed" — samme tavshedsform som resten af
       bølgen har fundet. Bundet lokalt.
       **Begge grene var utestede** — ingen test konstruerede servicen med en ML/LLM-tier.
       Fem shapes pinnet, og som i saga kørt mod den **gamle** kode først: 9/9 grønne dér
       også, hvilket er beviset for neutralitet frem for påstanden om den.
     - **P2-32 igen** i `unit_of_work.py` — **fjerde service af 7.**
     - `Result[Any].rowcount` (samme `sql_result.rowcount()`-helper som notification og
       budget, nu tredje kopi — værd at overveje som shared), merchant-repo hvor `model`
       havde to typer i to grene, og `RuleEngineProvider.get()` uden returtype bag en
       `# noqa: ANN201 — IRuleEngine protocol`, hvor annotationen bare var rigtig.
     - `transaction_id` fra en utypet event-dict: ignore, men **vagten er verificeret** frem
       for ræsonneret — `categorization_results.transaction_id` er `NOT NULL`, så en `None`
       ruller hele transaktionen tilbage frem for at skrive en NULL-auditrække.
     Kontrolleret begge veje, inkl. specifikt for mapperen: en felt-typo (`category.typ`)
     flagges nu, hvor `object` gjorde den usynlig. 130 tests grønne (125 + 5 nye).
   - Resterende: ingen. Hver service:
   `mypy` i dev-group, `[tool.mypy]`-blok kopieret fra analytics, `typecheck`-target,
   navn på CI-allowlisten. Blokeret indtil P3-23/P3-39: **banking, account**. Eget item:
   **gateway**.
   Dette trin skal ikke afsluttes i én session; gaten er allerede reel efter trin 4.
7. [x] **CLAUDE.md.** Erstat ASPIRATIONAL-noten med hvad der er sandt: hvilke services
   gaten dækker, at niveauet er default-mypy og ikke `--strict`, og at banking/account er
   udenfor med henvisning til P3-23. Samme sted: en linje om at
   `py.typed` er obligatorisk på nye shared-pakker.
   *Commit sidst i hver bølge, så noten aldrig overdriver dækningen.*

   Gjort 2026-07-27, efter kontrol C var kørt grøn mod et **grønt** run (8/4). Rækkefølgen
   viste sig at være det vigtigste ved trinnet: havde noten været skrevet før pushet, ville
   den have påstået dækning på et tidspunkt hvor master ikke kunne starte budget-service.

   **Bølgen lukkede med sin egen fejlmode i tredje forklædning.** E2E blev rød på
   categorization-pushet, men fejlen var budgets gate-commit fire commits tidligere — som
   sammen med tre andre aldrig havde haft en CI-kørsel. Et `-> None` tilføjet for
   `disallow_untyped_defs` dræbte containeren ved import, fordi
   `from __future__ import annotations` gør annotationen til `NoneType` og imagets FastAPI
   0.115.0 læser det som en response model på en 204. Se
   [fundet](../findings/2026-07-27-none-annotation-204-fastapi-split.md) → **P2-37**.

   Det væsentlige er ikke fixet, men mønstret: `make check` kørte `uv.lock` (0.136.3),
   containeren kørte `requirements.txt` (0.115.0). Tredje gang i denne ene plan at checken
   og virkeligheden læste fra hver sin kopi — efter `MYPYPATH`-mod-kildekode og budgets
   `PYTHONPATH`-mod-`contracts`. Gaten er altså reel for typer, men et grønt `check` er ikke
   et løfte om at imaget starter, og det står nu i CLAUDE.md.

   Ærligt om hvordan det blev fundet: kun fordi et E2E-job var rødt. Fire ugennemkørte
   commits på en lokal branch er en risiko uafhængigt af deres indhold.

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
   **Automatiseret: `make verify-typecheck-gate`** (`scripts/verify_typecheck_gate.py`).
   Kør den efter hver service der kommer på allowlisten — begge tal skal flytte sig, og
   scriptet læser den forventede allowliste ud af `ci.yml` frem for at have sin egen kopi.
   Kørt grøn 2026-07-27: run #239 (10/2) og run #240 (9/3, `c7438541`).
   **Bevist at den kan blive rød:** med `goal-service` midlertidigt tilføjet til
   allowlisten i `ci.yml` melder den `FAILED — goal-service is on the allowlist but
   emitted a ::notice`, exit 1. En kontrol der kun er set sige grøn er ikke en kontrol.
   Praktisk: ~15 anonyme API-kald per kørsel mod et loft på 60/t, hvilket er den bindende
   begrænsning under udrulningen. `gh auth login` én gang er nok — begge scripts falder
   tilbage til `gh auth token`, så ingen token behøver ligge i en dotfil.
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
