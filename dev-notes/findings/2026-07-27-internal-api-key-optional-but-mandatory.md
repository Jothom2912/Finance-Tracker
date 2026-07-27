---
title: INTERNAL_API_KEY er typet valgfri i 6 services, men obligatorisk i mindst 3
date: 2026-07-27
severity: LOW
area: cross, config
status: open
scheduled-as: P2-33
---

# `str | None` med en guard der gør den til `str` — seks steder, tre af dem uærlige

Fundet 2026-07-27 af P2-31's **anden** udrulningsservice. Efter
[den usande outbox-port](2026-07-27-outbox-port-declares-foreign-entity.md) fra den første
er det to repo-brede kontraktfejl på to services. Det er ikke tilfældigt: gaten er den
første maskine der læser annotationerne som påstande i stedet for som kommentarer.

## Hvad

`notification-service/app/config.py:11`:

```python
INTERNAL_API_KEY: str | None = None
...
if not settings.INTERNAL_API_KEY:
    raise ValueError("INTERNAL_API_KEY must be set in environment variables.")
```

Guarden ligger på modulniveau, så den kører ved import af `app.config`. Feltet er dermed
aldrig `None` for nogen der kan læse `settings` — men typen siger noget andet, og
`AccountServiceAdapter` kræver `str`:

```
app/workers/notification_consumer.py:63: error: Argument "api_key" to
  "AccountServiceAdapter" has incompatible type "str | None"; expected "str"  [arg-type]
```

## Omfang

`INTERNAL_API_KEY: str | None = None` står i **seks** services: banking, categorization,
goal, notification, transaction, user. Tre af dem sender værdien direkte ind i en `str`-parameter:

| Service | Kaldsted |
|---|---|
| banking | `app/dependencies.py:51` |
| banking | `app/workers/sync_scheduler.py:150` |
| goal | `app/dependencies.py:17` |
| notification | `app/workers/notification_consumer.py:63` |

To services gør det allerede rigtigt, og de gør det på hver sin måde:

- `transaction-service/app/adapters/outbound/categorization_client.py:37` bygger headeren
  betinget — dér **er** nøglen reelt valgfri, og typen er sand.
- `account-service/app/config.py:82` bruger `os.getenv` og tjekker på kaldsstedet
  (`internal_api.py:20`).

Så det er ikke ét mønster der er forkert seks steder. Det er to legitime mønstre —
"obligatorisk" og "valgfri, degrader pænt" — hvor det obligatoriske er skrevet med det
valgfries type.

## Hvorfor det ikke er rettet i notification-service

Fristelsen var at gøre feltet påkrævet (`INTERNAL_API_KEY: str`) i den commit der satte
servicen på gaten. Det ville have været en sandere type, og det ville have fulgt
`JWT_SECRET` i samme fil, som P1-15 gjorde påkrævet af netop denne grund.

To ting talte imod:

1. **Det løser en sjettedel og skaber en afvigelse.** Notification ville blive den eneste
   service med et påkrævet felt, mens goal og banking rammer nøjagtig samme fejl senere i
   udrulningen. Så var den repo-brede beslutning truffet implicit, i en commit om noget andet.
2. **P2-31's non-goals forbyder det.** "En typefejl der kræver runtime-ændring rettes ikke
   her." Reglen findes for at en gate-udrulning ikke bliver en trojansk hest for
   adfærdsændringer, og den første gang den koster noget er den forkerte gang at bøje den.

Behandlet som P2-32 blev det: begrundet `# type: ignore[arg-type]` med reference hertil, og
`warn_unused_ignores = true`, så linjen fejler af sig selv når feltet gøres påkrævet.
Kontrolleret begge veje — uden ignore rød med `[arg-type]`, med ignore grøn.

## Hvad P2-33 skal beslutte

Ikke "gør feltet påkrævet", men **hvilke af de seks der hører til hvilket mønster**:

- Obligatorisk → `INTERNAL_API_KEY: str` uden default. Guarden bliver stående, fordi den
  fanger tom streng, som pydantic accepterer. Omkostning: manglende env-var giver
  `ValidationError` frem for den forklarende `ValueError` — begge fejler ved opstart.
- Reelt valgfri → transaction-mønsteret: betinget header, og en eksplicit beslutning om
  hvad servicen gør uden nøgle.

Det er en beslutning der fortjener at blive truffet én gang med alle seks på bordet.
