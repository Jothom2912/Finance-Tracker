---
title: "SerializableEvent krævede settable attributter — så BaseEvent opfyldte ikke sin egen Protocol"
date: 2026-07-27
severity: LOW
area: cross, contracts
status: resolved
resolved-by: P2-31 trin 6 (saga-service), 2026-07-27 — read-only properties + `correlation_id: str | None` i `finans-tracker-messaging` 0.1.2; se [plans/2026-07-27-p231-static-typecheck-gate.md](../plans/2026-07-27-p231-static-typecheck-gate.md)
---

# Protocol'en var strengere end sin egen reference-implementation

Fundet 2026-07-27 af P2-31's udrulning til `saga-service`. Rettet samme dag i shared
(`finans-tracker-messaging` 0.1.1 → 0.1.2), fordi fixet var rent typningsmæssigt.

## Hvad

`shared/messaging/messaging/rabbitmq.py`:

```python
@runtime_checkable
class SerializableEvent(Protocol):
    """Structural type matched by ``contracts.base.BaseEvent``. ...
    any object with ``event_type``, ``correlation_id`` and ``to_json()``
    publishes fine."""

    event_type: str
    correlation_id: str
```

Et **almindeligt attribut** i en Protocol kræver et *settable* attribut af
implementationen. Men `contracts.base.BaseEvent` er `model_config =
ConfigDict(frozen=True)`. Docstringens påstand var derfor usand: reference-implementationen
opfyldte ikke protokollen. Målt med en probe i sagas venv:

```
error: Argument 1 to "want" has incompatible type "MyEvent"; expected "SerializableEvent"
note: Protocol member SerializableEvent.correlation_id expected settable variable,
      got read-only attribute
note: Protocol member SerializableEvent.event_type expected settable variable, ...
```

hvor `MyEvent` blot er `class MyEvent(BaseEvent)`. Og "any object … publishes fine" var
dobbelt usandt: intet *frozen* objekt kunne opfylde den.

Samme fil var desuden internt uenig om `correlation_id`:

| Sted | Type |
|---|---|
| `SerializableEvent.correlation_id` | `str` |
| `OutboxEntry.correlation_id` | `str \| None` |
| `outbox_events.correlation_id`-kolonnen | `nullable=True` |
| `OutboxRepository._build` | `getattr(event, "correlation_id", None)` |

Tre af fire sagde optional. Protokollen var det ene sted der påstod obligatorisk — og
`_build`s defensive `getattr` med `None`-default er koden der ikke tror på sin egen
annotation.

## Hvorfor det ikke var en live bug

Protocols håndhæves ikke ved runtime, og der findes **ingen** `isinstance`-brug af
`SerializableEvent` i repoet (`@runtime_checkable` er dekoration uden kalder). Begge læsere
tolererer `None` i forvejen: `_build`s `getattr`-default og `RabbitMQPublisher`s
log-argument. Så ingen adfærd afhang af det. LOW.

## Hvorfor kun saga så det

Det er den del der er værd at bære videre. `budget-service` og `user-service` kalder også
`outbox.add(event, ...)` med rigtige contracts-events, og deres gate var grøn. Grunden er at
de kalder gennem **deres egen** `IOutboxRepository`-port, hvor
[P2-32-ignoren](2026-07-27-outbox-port-declares-foreign-entity.md) allerede står på
tilskrivningen:

```python
self.outbox = OutboxRepository(session, OutboxEventModel)  # type: ignore[assignment]
```

Efter den linje er `self.outbox` typet som porten, ikke som shared's klasse, så kaldet
tjekkes mod portens signatur. **Én begrundet ignore skjulte en anden, urelateret usand
kontrakt.** Saga har ingen sådan ignore — dens adapter wrapper shared eksplicit i
`self._inner` — så den var den første service hvor mypy kunne se igennem.

Lektionen er ikke "ignores er dårlige", men at en ignore har en bredde man ikke vælger:
`[assignment]` på en tilskrivning slår typen fast for *alle* senere kald på det navn. Det er
et argument for at ignoren skal sidde så snævert som muligt, og for at et item som P2-32 ikke
bare er hygiejne — den skjuler aktivt.

## Fix

```python
@property
def event_type(self) -> str: ...

@property
def correlation_id(self) -> str | None: ...
```

Read-only, fordi intet i pakken skriver til dem — det er både det der gør frozen
implementationer lovlige og den præcise beskrivelse af hvad publisher og `_build` gør.
`str | None` for at matche de tre andre steder.

Verificeret:

- Proben ovenfor: `MyEvent()` accepteres nu; sagas `_CommandEnvelope` ligeså.
- `isinstance(obj, SerializableEvent)` virker stadig (properties tælles med i
  `__protocol_attrs__`) — tjekket, selvom ingen kalder det.
- Alle 5 gatede services stadig `Success`, og **P2-32-ignorerne blev ikke ubrugte**
  (`warn_unused_ignores` ville have fejlet) — det er to forskellige fejl, ikke én.
- 791 tests grønne på tværs af de 7 messaging-dependents; 45 i shared selv.

## Omkostning der blev accepteret

Versionsbump + re-lock af 7 services midt i P2-31's udrulningsbølge. Trin 1 etablerede at
path-deps installeres som kopier, så et bump er det eneste der får ændringen ud; her er det
efterprøvet per service, at både versionen **og** `property`-formen faktisk nåede venv'et —
ikke kun at `uv lock` skrev et nyt tal.

## Relateret

- [P2-31-planen](../plans/2026-07-27-p231-static-typecheck-gate.md) — trin 6, saga-service.
- [outbox-porten erklærer en fremmed entitet](2026-07-27-outbox-port-declares-foreign-entity.md)
  / P2-32 — ignoren der skjulte dette.
- [Optional id](2026-07-27-optional-id-hides-unpersisted-entity.md) / P2-35 — samme
  bølge, samme klasse af usand annotation.
