---
title: Goal bygges med to forskellige runtime-typer af sine to repositories
date: 2026-07-27
severity: MEDIUM
area: goal, domain
status: open
scheduled-as: P2-34
---

# Samme entitet, `float` fra det ene repository og `Decimal` fra det andet

Fundet 2026-07-27 da `goal-service` blev målt for typecheck-gaten (P2-31 trin 6). Servicen
gav **23 fejl mod tabellens 1** — og 1-tallet var selv en målefejl (`Source file found twice`,
et artefakt af `MYPYPATH` mod kildekoden). Fem af de 23 er ægte; disse er de alvorligste.

## Hvad

`Goal` er én dataclass med `target_amount: float` og `current_amount: float`. To
repositories konstruerer den, og de er uenige om hvad den indeholder:

| Repository | Kode | Faktisk runtime-type |
|---|---|---|
| `postgres_goal_repository.py:100` | `target_amount=float(model.target_amount)` | `float` |
| `postgres_goal_allocation_repository.py:50` | `target_amount=Decimal(str(model.target_amount))` | `Decimal` |

Annotationen siger `float` i begge tilfælde. mypy fanger kun den ene, fordi den anden
konverterer *til* den erklærede type.

Kilden til forvirringen er et lag længere nede: `models.py:17-18` erklærer
`Mapped[float]` på en `Numeric(12, 2)`-kolonne. SQLAlchemy leverer `Decimal` for `Numeric`,
så modellens egen annotation er usand, og begge repositories "retter" den — bare hver sin vej.

At `increment_current_amount` (`postgres_goal_allocation_repository.py:42`) allerede
defensivt gør `Decimal(str(model.current_amount)) + amount` tyder på at nogen har mødt
problemet før og løst det lokalt.

## Observerbar konsekvens

`application/service.py:188-189` serialiserer beløb til event-payloads med `str()`:

```python
target_amount=str(goal.target_amount),
current_amount=str(goal.current_amount),
```

`str(Decimal("100.00"))` er `"100.00"`. `str(100.0)` er `"100.0"`. **Samme mål giver to
forskellige strenge på RabbitMQ, afhængigt af hvilket repository der læste det.**

Numerisk er de ens, og en consumer der parser til `Decimal` eller `float` ser ingen forskel.
Det er derfor den ikke er HIGH. Men strengen er ikke kun et tal: bliver den nogensinde del
af en dedup-nøgle, en idempotens-nøgle eller en tekstuel sammenligning, er de to former
ikke ens. Read-modeller self-healer ikke mod den slags — jf. ES-fantomrækkerne.

Den anden latente risiko er aritmetik på tværs: `Decimal + float` rejser `TypeError` i
Python. I dag er hver `Goal`-instans internt konsistent, fordi ét repository bygger den
færdig. Det holder kun så længe ingen kombinerer en `Goal` fra det ene repository med et
beløb fra det andet.

## Relateret i samme service: `Goal.status` er en magic string

`entities.py:21` erklærer `status: str | None`, selvom `GoalStatus` findes lige ovenfor.
Det er CLAUDE.md's anti-pattern-liste ordret: *"Magic strings for status/typer (brug enums)"*.

Det virker i dag **udelukkende** fordi `GoalStatus(str, enum.Enum)` gør
`"paused" == GoalStatus.PAUSED` sand. Var `GoalStatus` en almindelig `Enum`, ville
`effective_status`' sammenligninger stille og roligt være falske, og metoden ville aldrig
returnere `PAUSED`. Korrektheden hviler på en arvedetalje, ikke på en beslutning.

## Hvorfor goal-service ikke kom på gaten

De fem ægte fejl kan ikke lukkes med `# type: ignore` uden at fire af dem sidder på det
samme underliggende pengetypnings-problem. En gate hvis første handling i en service er at
tie om et pengeproblem lærer læseren at `ignore` er normalen. Planens risiko-klausul dækker
netop dette: *"en service med uventet mange fejl bliver et selvstændigt item i stedet for at
trække bølgen."*

Til sammenligning fik `user-service` og `notification-service` hver **én** begrundet ignore,
hver med sit eget item og en kontrol i begge retninger.

## Hvad P2-34 skal beslutte

1. **`Decimal` eller `float` for penge i denne service** — og så det samme hele vejen:
   `models.py`s `Mapped[...]`, `Goal`, DTO'erne og event-serialiseringen. `Decimal` er det
   rigtige for beløb, men det er et valg der rører event-payloads, så det skal træffes
   bevidst og ikke pr. repository.
2. **Event-serialiseringen eksplicit** — `str()` på et beløb er ikke et format. Vælg ét
   (fx altid to decimaler) frem for at arve `repr`-adfærd fra den type der tilfældigvis kom
   ud af DB'en.
3. **`Goal.status: GoalStatus | None`** — og hvad der sker med rækker i DB'en hvis strengen
   dér ikke er en gyldig enum-værdi.
4. **De øvrige 18 fejl** følger recipen fra notification-service: 15 mekaniske,
   2 → [P2-32](2026-07-27-outbox-port-declares-foreign-entity.md),
   1 → [P2-33](2026-07-27-internal-api-key-optional-but-mandatory.md). Derudover arver
   `AccountServiceAdapter` ikke `IAccountPort`, selvom den implementerer begge metoder —
   samme form som P2-32, men her er fixet én linje uden runtime-effekt.
