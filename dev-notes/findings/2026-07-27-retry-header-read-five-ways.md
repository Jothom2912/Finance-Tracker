---
title: "x-retry-count læses på fem forskellige måder; to af dem kaster inde i retry-handleren"
date: 2026-07-27
severity: MEDIUM
area: cross, messaging
status: open  # transaction-service rettet; shared + analytics ×2 + banking står tilbage
scheduled-as: P2-36
---

# Samme header, fem stavemåder, og en poison-loop i to af dem

Fundet 2026-07-27 af P2-31's udrulning til `transaction-service`: 20 af servicens 26
mypy-fejl havde denne ene rod. Rettet i transaction-service; de tre øvrige steder er
uberørte → **P2-36**.

## Hvad

aio-pika typer en header-værdi som hele AMQP-unionen — `bytes | bytearray | Decimal |
FieldArray | FieldTable | float | int | str | datetime | None` — fordi wire-formatet
bestemmer, ikke os. Repoet læser `x-retry-count` fem forskellige steder, på fire
forskellige måder:

| Sted | Læsning | `"3"` (str) | `None` | `"abc"` |
|---|---|---|---|---|
| `shared/messaging/consumer.py:223` | `int(x)` | 3 | TypeError | ValueError |
| `analytics/projection_consumer.py:140` | `int(str(x))` | 3 | 0 | ValueError |
| `analytics/embedding_consumer.py:128` | `int(str(x))` | 3 | 0 | ValueError |
| `transaction/categorized_consumer.py:100` | `int(x)` | 3 | TypeError | ValueError |
| `transaction/saga_command_consumer.py:100` | `isinstance(bytes)` → rå `>=` | **TypeError** | **TypeError** | **TypeError** |
| `banking/saga_command_consumer.py:189` | identisk med ovenstående | **TypeError** | **TypeError** | **TypeError** |

De to saga-consumere special-caser `bytes` og sammenligner derefter den rå værdi med en
int. Målt: `'3' >= 3` → `TypeError: '>=' not supported between instances of 'str' and 'int'`.
Koden håndterer altså den ene indpakning nogen engang så, og ikke den anden.

## Hvorfor det er MEDIUM og ikke LOW

Alle seks læsninger står **inde i** en `except Exception`-retry-handler. En exception dér
betyder at beskeden hverken ackes eller republishes — så broker'en redeliverer den for evigt
**uden at tælleren rykker**. Retry-ladderen kan ikke terminere, og `MAX_RETRIES` nås aldrig.
En poison-loop er en værre fejl end den der var under behandling.

Det er derfor dette ikke bare er upræcished: den forkerte læsning konverterer en
enkeltstående handler-fejl til en uendelig redelivery.

## Hvorfor det ikke er en live bug i dag

Hver eneste **writer** i repoet sætter en `int` (`headers["x-retry-count"] = retry_count`,
6 steder), og AMQP round-tripper ints som ints. Så unionen er bredere end det vi selv
producerer, og `str`-grenen nås ikke af vores egne republishes. Den er nåelig hvis noget
uden for koden sætter headeren — en shovel, management-pluginets redelivery, eller en
fremtidig publisher der stringificerer.

Det er præcis den formuleringen der gør fundet værd at skrive ned frem for at rette i
tavshed: **"nås ikke i dag" er en egenskab ved kalderne, ikke ved koden**, og det er samme
form som [sync-trigger-fundet](2026-07-27-sync-trigger-double-value.md), hvor en docstring
påstod noget om kalderne uden at have læst dem.

## Rettet (transaction-service)

Én helper, `app/workers/retry_headers.py`, brugt af begge consumere. Alt der ikke er et
brugbart tal behandles som `0`, altså "første forsøg": ladderen rykker normalt og
terminerer ved `MAX_RETRIES` i stedet for at spinne.

Bevidst adfærdsdelta, ikke kun en typerettelse: shapes der før kastede (`None`,
non-numerisk `str`, `list`, `dict`, `datetime`) returnerer nu 0. Det bytter en uendelig
redelivery for en retry-serie der slutter — samme "starter forfra"-udfald, uden at dræbe
handleren.

To detaljer helperen fanger, som ingen af de fem stavemåder gjorde:

- **`bool` er en `int`-subklasse.** En `True`-header ville tavst betyde "1 forsøg".
  Eksplicit 0.
- **`Decimal` er i unionen.** Fanget af helperens *egen test* inden den blev committet —
  første version faldt igennem til 0 for et fuldt gyldigt tal.

Dækning: 16 unit tests pinner alle shapes i tabellen. Værd at være ærlig om at
**kaldstederne selv var og er utestede** — der findes ingen test i nogen af de to
consumere der rører retry-stien, hvilket er hvorfor forskellen mellem de to stavemåder
kunne leve i samme fil-mappe.

## Ikke rettet → P2-36

`shared/messaging/consumer.py`, `analytics/projection_consumer.py`,
`analytics/embedding_consumer.py`, `banking/saga_command_consumer.py`.

Banking er den samme kopi-pastede kode som transactions saga-consumer, altså samme
TypeError. Bemærk hvad det siger om P2-31's dækning: **banking er servicen hvor
[den motiverende fejl](2026-07-27-sync-trigger-double-value.md) levede, den kan endnu ikke
gates (P3-23/P3-39), og her er nummer to latent fejl gaten ikke kan se dér.** Argumentet for
at prioritere P3-23 er nu målt to gange, ikke ræsonneret.

Den rigtige form for P2-36 er formodentlig at helperen flytter til `shared/messaging` og de
fem steder kalder den — men det er et versionsbump og et re-lock, og valget hører til i
itemet.

## Relateret

- [P2-31-planen](../plans/2026-07-27-p231-static-typecheck-gate.md) — trin 6,
  transaction-service.
- [SerializableEvent](2026-07-27-serializable-event-demands-mutable-attrs.md) — samme
  bølge, samme pakke, også en kontrakt der var usand om sig selv.
