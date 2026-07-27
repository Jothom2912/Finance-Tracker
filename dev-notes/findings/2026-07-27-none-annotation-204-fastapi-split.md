---
title: "En returtype tilføjet for typecheck-gaten dræbte budget-services container — og gatens egen test kunne ikke se det"
date: 2026-07-27
severity: HIGH
area: budget, CI, deps
status: resolved
resolved-by: eksplicit `response_model=None` på de tre 204-ruter (2026-07-27) — symptomet lukket og verificeret mod begge FastAPI-versioner; rodårsagen (requirements.txt ≢ uv.lock) er P2-37
scheduled-as: P2-37
---

# `-> None` på en 204-rute + gammel FastAPI i imaget = død ved import

Fundet 2026-07-27 da E2E-jobbet blev rødt på `302cc437`. Fejlen var **ikke** i den commit,
men i `7d938fdb` (budget-service på typecheck-gaten) — fire commits lå kun lokalt og nåede
aldrig CI, så pushet af categorization var den første kørsel der dækkede dem.

## Hvad

`budget-service` kunne ikke importere sit eget `app.main`:

```
File "/app/app/adapters/inbound/monthly_budget_api.py", line 91, in <module>
  @router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
File ".../fastapi/routing.py", line 507, in __init__
  assert is_body_allowed_for_status_code(
AssertionError: Status code 204 must not have a response body
```

Containeren døde i uvicorns import, altså før noget healthcheck kunne sige fra.

## Roden er en trevejs-interaktion — ingen af delene er forkert alene

1. Filen har `from __future__ import annotations`. Det gør `-> None` til en **streng**, som
   FastAPI evaluerer med `get_type_hints`, og dér normaliseres `None` til `NoneType`.
2. **FastAPI 0.115.0** behandler `NoneType` som en rigtig response model — den er truthy — og
   asserter derfor på en statuskode der ikke må have body. Nyere FastAPI har rettet det.
3. **P2-31 tilføjede `-> None`** på tre 204-ruter for at opfylde `disallow_untyped_defs`.

Punkt 1 og 2 havde ligget der i månedsvis uden konsekvens. Punkt 3 var mekanisk, korrekt og
gennemgået. Fejlen opstod i mødet.

## Hvorfor CI var grøn — den del der er værd at bære videre

Det fristende svar er "der manglede en test der importerer appen". Det er forkert:
`tests/integration/test_monthly_budget_api.py` og `test_rest_api.py` importerer begge
`app.main`. **Testene ramte præcis det modul der dør i produktion.**

De bestod fordi de importerede det under en anden FastAPI:

| | Hvad kører den | FastAPI |
|---|---|---|
| `pytest`, `mypy`, `make check` | `uv.lock` via `uv run` | **0.136.3** |
| Containeren | `requirements.txt` via `pip install` i `Dockerfile` | **0.115.0** |

To sandhedskilder for én afhængighed. Gaten validerede altså kode mod et andet FastAPI end
deploy kører, og et grønt `make check` sagde intet om det image der starter.

Det er tredje forklædning af samme form i P2-31 alene:

- trin 2: `MYPYPATH` mod kildekoden vs. den installerede pakke → `Source file found twice`
- budget-service: `PYTHONPATH=../../shared/contracts` vs. den installerede `contracts`
- her: `requirements.txt` vs. `uv.lock`

Hver gang er symptomet forskelligt, og hver gang er diagnosen "checken og virkeligheden
læser fra hver sin kopi".

## Omfang

Sweep efter 204/304-ruter med `-> None` i filer med `from __future__ import annotations`:
8 kandidater i 3 services. Kun **budgets 3 er nye fra P2-31**; categorizations 3 og
transactions 2 er ældre, og de services har ingen pinnet `fastapi` i `requirements.txt` —
deres images løser en nyere version og rammes derfor ikke.

`fastapi==0.115.0` er kun pinnet i **budget** og **banking**. Banking er ikke gatet (blokeret
af P3-23), og det er den næste fælde: gates banking senere, og får en 204-rute et `-> None`,
er det den samme død. Det er grunden til at dette fund findes frem for tre linjers fix.

## Fix

`response_model=None` eksplicit på de tre ruter, med begrundelsen i koden så ingen "rydder op"
i den. Verificeret som rigtig frem for antaget:

- `app.main` importerer nu OK under **både** 0.115.0 og 0.136.3.
- Kontrol: uden fixet fejler 0.115.0 stadig med samme assertion på den rigtige app, ikke kun
  i en repro. En rettelse der kun er set virke er ikke verificeret.
- 117 tests grønne (61 + 56), `make check` grøn.

Valgt frem for at bumpe `requirements.txt` til lockens version: den ville rette drift'en, men
ændre hele servicens deployede afhængighedssæt i ét hug, og `requirements.txt` er
sandsynligvis drevet på mere end `fastapi`. Symptomet lukkes nu; roden får sit eget item.

**Metode-note.** Min første repro sagde "begge FastAPI-versioner er OK" og ville have
frikendt versionssplittet helt. Den manglede `from __future__ import annotations` — altså en
repro der ikke kunne reproducere. Fjerde gang i denne plan at målingen var blind for
spørgsmålet, og den eneste grund til at det blev fanget er at svaret modsagde et CI-log jeg
allerede havde læst.

## Relateret

- [P2-31-planen](../plans/2026-07-27-p231-static-typecheck-gate.md) — trin 6, budget-service.
- **P2-37**: én install-sti per service. **Korrektion 2026-07-28** — denne linje sagde
  oprindeligt "håndhæv `requirements.txt` ≡ `uv.lock` i CI; `make freeze` findes allerede i
  hver service, intet tjekker at den er kørt". Begge led var usande, og målingen er nu gjort:
  - `freeze:`-target findes i **3 af 15** services (transaction, categorization, user) — og
    alle tre bygger med `uv sync --frozen` og har ingen `requirements.txt` på disk. Targettet
    er levn fra før Dockerfile-migrationen og har intet at gøre. Ingen af de tre services der
    faktisk `pip install`er har et.
  - **9 services** bygger med `uv sync --frozen --no-dev` → image og tests læser samme
    lockfile, og drift er strukturelt umuligt. **3** bygger med `pip install -r
    requirements.txt`: account, banking, budget.
  - Drift-betingelsen — *begge* filer til stede — findes derfor i **præcis én** service:
    **budget**. account og banking har ingen lockfile, så de kan ikke drifte; de har én
    usandt-låst kilde i stedet for to uenige (account pinner ikke `fastapi` overhovedet, så
    dens image er ikke reproducerbart).

  Fixet er dermed ikke en ækvivalens-check, men at give budget samme Dockerfile-form som de 9
  (`uv sync --frozen`, shared som path-deps under `/shared/*` — mønsteret findes og virker),
  slette dens `requirements.txt`, og lægge en vagt i `scripts/compose_check.py` mod at en
  service har begge filer. Så forsvinder fejlklassen frem for at blive overvåget. De 3 døde
  `freeze`-targets kan slettes samtidig. account og banking hører under P3-23/P3-01, hvor de
  får en lockfile — og bemærk at bankings `fastapi==0.115.0`-pin er den fælde `## Omfang`
  ovenfor beskriver, altså et *særskilt* problem fra drift'en.
- [per-worker image staleness](2026-07-25-per-worker-image-staleness.md) — samme familie:
  det der køres er ikke det der blev testet.
