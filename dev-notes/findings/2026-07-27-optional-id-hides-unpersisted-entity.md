---
title: "Optional[int] id gør persisteret og upersisteret entitet til samme type — i 4 services"
date: 2026-07-27
severity: LOW
area: cross, domain
status: open
scheduled-as: P2-35
---

# `id: Optional[int]` på domain-entiteter, men alle læse-stier behandler den som `int`

Fundet 2026-07-27 af P2-31's udrulning til `budget-service`. Efter at 21 af 24 mypy-fejl var
mekaniske, var de sidste tre alle den samme rod.

## Hvad

Domain-entiteterne modellerer id som `Optional[int]`, fordi entiteten også findes *før* den
er skrevet til databasen:

```python
@dataclass
class MonthlyBudget:
    id: Optional[int]
```

Men hver enkelt læse-sti tager entiteten fra et repository, hvor id **altid** er sat, og
sender den videre til noget der kræver `int`:

```
app/application/service.py:96                 BudgetResponseDTO(id=budget.id, ...)
app/application/monthly_budget_service.py:411 MonthlyBudgetResponse(id=budget.id, ...)
app/application/monthly_budget_service.py:320 mark_closed(budget.id)
```

Én type dækker altså to tilstande der har forskellige invarianter, og typen fortæller
kaldstedet det svagere af de to. Ingen af de tre er en live bug i dag — alle tre steder
kommer `budget` fra et repository-opslag, hvor rækken findes.

## De tre kaldsteder er ikke lige uskyldige

Det er den del der er værd at bære videre, og den grund til at fundet findes frem for bare
tre ignores:

- **De to DTO-steder har allerede en runtime-vagt.** `BudgetResponseDTO.id` og
  `MonthlyBudgetResponse.id` er `id: int` i pydantic, så `id=None` fejler som
  `ValidationError` før noget forkert kan nå brugeren. Typefejlen er ren dokumentations-gæld.
- **`mark_closed(budget.id)` har ingen.** SQLAlchemy oversætter `WHERE id == None` til
  `WHERE id IS NULL`, så et `None` ville ramme 0 rækker, `closed` bliver `False`, og servicen
  kaster `MonthlyBudgetAlreadyClosed(month, year)`. Altså **409 "måneden er allerede lukket"
  for en måned der aldrig blev lukket** — en fejlbesked der peger væk fra årsagen. Samme form
  som de andre løgne P2-31 har fundet: koden er tavs på den måde der koster mest at
  fejlsøge.

Forskellen forsvinder, hvis nogen senere begynder at bygge entiteten i hånden i en use case.

## Omfang

`grep 'id: Optional\[int\]|id: int | None' services/*/app/domain/entities.py`:
budget (3 entiteter), categorization (6), account (2), goal (1). Det er altså ikke en
budget-særhed, men et repo-bredt modellerings-valg → eget item.

## Hvorfor det ikke rettes her

Fixet er en runtime-ændring, og P2-31's non-goals siger eksplicit at sådan en bliver et
finding plus en begrundet `# type: ignore`, ikke en drive-by. Der er mindst tre kandidater,
og valget mellem dem hører til i et item med hele omfanget på bordet:

1. **`assert budget.id is not None`** på kaldstederne. Billigst, men flytter kun løgnen til
   en runtime-påstand og gør `assert` til domænelogik (fjernes af `python -O`).
2. **Split typen**: `MonthlyBudget` (upersisteret, ingen id) og `PersistedMonthlyBudget`
   (`id: int`), hvor repository'et returnerer den sidste. Ærligt, men to typer per entitet
   på tværs af 4 services.
3. **Drop `Optional` og lad upersisterede entiteter bære en sentinel** — nej: det er præcis
   det magic-value-antipattern CLAUDE.md forbyder andre steder.

Kandidat 2 er den der matcher hexagonal-tænkningen, og den der koster mest. Beslut i P2-35.

## Behandling nu

`# type: ignore[arg-type]` på alle tre linjer med henvisning hertil. `warn_unused_ignores`
er slået til i budgets mypy-config, så linjerne fejler af sig selv den dag P2-35 lander.

## Hvorfor dette *ikke* er en goal-service

Værd at være præcis om, siden [P2-34](2026-07-27-goal-entity-two-runtime-types.md) fik
modsat dom på et overfladisk lignende grundlag ("flere ignores på én rod"). Antallet var
ikke kriteriet dér, og er det ikke her:

| | goal-service (P2-34, trukket ud) | budget-service (her, gated) |
|---|---|---|
| Divergens i output | ja — `"100.0"` mod `"100.00"` i event-payloads | nej, ingen målt |
| To kilder | to repositories bygger `Goal` med hver sin talttype | én kilde, én type |
| Runtime-vagt | ingen | pydantic på 2 af 3 kaldsteder |
| Fejlklassen | penge-typning, altså korrekthed | persisteret/upersisteret, altså præcision |

Kort: goal-services fejl kunne *ses* i data der forlod servicen. Denne kan kun ses af en
typechecker. Havde `mark_closed`-stien været nåelig, ville dommen være den anden.

## Relateret

- [P2-31-planen](../plans/2026-07-27-p231-static-typecheck-gate.md) — trin 6, budget-service.
- [outbox-porten erklærer en fremmed entitet](2026-07-27-outbox-port-declares-foreign-entity.md)
  / P2-32 — samme service, samme slags usande annotation, også fundet af gaten.
