---
title: Outbox-porten erklærer en anden klasse end adapteren leverer — i 7 services
date: 2026-07-27
severity: LOW
area: cross, contracts
status: open
scheduled-as: P2-32
---

# `IOutboxRepository` lover sin egen `OutboxEntry`; adapteren returnerer shared's

Fundet 2026-07-27 af P2-31's **første** udrulningsservice. Det er værd at sige højt:
gaten havde ikke kørt på andet end pilotservicen i en time, før den fandt en port hvis
kontrakt aldrig har været sand.

## Hvad

`user-service`s `app/application/ports/outbound.py:54`:

```python
async def fetch_pending(self, batch_size: int = 10) -> list[OutboxEntry]: ...
```

hvor `OutboxEntry` er `app.domain.entities.OutboxEntry`. Men det objekt der tilskrives
porten i `app/adapters/outbound/unit_of_work.py:28` er shared's `messaging.OutboxRepository`,
hvis `fetch_pending` returnerer `messaging.outbox.OutboxEntry`. **To forskellige klasser med
samme navn.**

mypy's fejlbesked er selv et lille kuriosum, fordi den trykker begge typer ud og de er
tekstuelt identiske:

```
note: Following member(s) of "OutboxRepository" have conflicts:
note:     Expected:
note:         def fetch_pending(self, batch_size: int = ...) -> Coroutine[Any, Any, list[OutboxEntry]]
note:     Got:
note:         def fetch_pending(self, batch_size: int = ...) -> Coroutine[Any, Any, list[OutboxEntry]]
```

## Hvorfor det ikke er en live bug

Felterne er identiske — begge er `@dataclass(frozen=True)` med de samme 10 felter i samme
rækkefølge (shared har derudover `slots=True`). Outbox-publisher-workeren læser attributter,
så duck-typing bærer det. Målt: intet fejler i dag, og user-services 48 tests er grønne både
før og efter.

Det er derfor LOW. Men porten er **usand**, og det er den slags usandhed der bliver dyr præcis
når nogen begynder at stole på den: tilføj et felt til den ene klasse, og den anden følger
ikke med.

## Hvorfor duplikatet findes (og ikke bare skal slettes)

Det oplagte fix — slet `app/domain/entities.OutboxEntry` og importér shared's i porten — er
**forkert**. Det ville gøre domænelaget afhængigt af `messaging`, altså infrastruktur, hvilket
er det pytest-archon findes for at forhindre. Duplikatet er den hexagonale grænse, ikke sjusk.

Det manglende led er en **mapping i adapteren**: shared's `OutboxEntry` → domænets. Det er en
runtime-ændring, og porten findes som `ABC` i **7 services** (banking, budget, categorization,
goal, saga, transaction, user), så det er ikke en drive-by. → **P2-32**.

Bemærk hvad der *ikke* er problemet: jeg prøvede at gøre porten til en `Protocol` for at se om
uoverensstemmelsen blot var nominel. Det er den ikke — Protocol-versionen fejler med samme
besked. ABC-vs-Protocol er et selvstændigt spørgsmål og ikke dette.

## Behandling nu

`# type: ignore[assignment]` på tilskrivningen, med begrundelse og henvisning hertil i koden.
`warn_unused_ignores = true` er slået til i user-services mypy-config, så **linjen fejler af
sig selv den dag mappingen lander** — ignoren kan ikke blive glemt affald.

## Hvad det siger om P2-31

Fundet er ikke en typefejl der ville have brudt noget i drift. Det er en **falsk kontrakt**:
en annotation der påstår noget om kode ingen havde verificeret. Det er samme form som
[sync-trigger-fundet](2026-07-27-sync-trigger-double-value.md) — porten-docstringen dér skrev
"both callers already pass `SyncTrigger` members" uden at have læst kalderne. Forskellen er
at denne blev fanget af en maskine i stedet for af to dages brudte bank-syncs.

## Relateret

- [ingen typecheck nogen steder](2026-07-27-sync-trigger-double-value.md) / P2-31 — gaten der
  fandt dette.
- `patterns/transactional-outbox.md` — user-service er pattern-dokumentets
  reference-implementation, så porten bør rettes dér først når P2-32 tages.
