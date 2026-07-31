---
title: Én aktiv saga-række med et ukendt saga_type crash-looper saga-timeout-workeren permanent
date: 2026-07-31
severity: medium
area: [saga, resilience]
status: open
backlog-items: [P3-59]
related:
  - ../plans/2026-07-31-p359-request-path-logging.md
---

# Én aktiv saga-række med et ukendt `saga_type` crash-looper saga-timeout-workeren permanent

Fundet 2026-07-31 under P3-59's fase 2, ikke ledt efter. Jeg indsatte en probe-række i
`saga_instances` for at kunne drive saga-servicens "korrupt context"-403 fra en HTTP-request.
Rækken fik `saga_type='p359_probe'` og `status='started'`. Inden for 30 sekunder var
`saga-timeout-worker` i restart-loop, og `compose-state-check` blev rød:

```
compose-state-check: 1 of 53 containers are not alive:
  saga-timeout-worker (finance-tracker-saga-timeout-worker-1): state=restarting
```

**Proben var min fejl. Fragiliteten den afdækkede er ikke.**

## Mekanismen

`orchestrator.py:185` i `check_timeouts`:

```python
for saga_id in stale_ids:
    saga = await self._uow.sagas.get_by_id(saga_id, for_update=True)
    if saga is None or not saga.is_active or not self._is_stale(saga, cutoff):
        continue

    definition = self._registry.get(saga.saga_type)   # <-- kaster UnknownSagaType
```

`_registry.get` (`orchestrator.py:34`) kaster `UnknownSagaType`, og der er **ingen `except`
nogen steder i kaldekæden**. Exceptionen propagerer:

`check_timeouts` → `_check_once` (`saga_timeout_worker.py:49`) → `run_forever` (`:42`) →
`main` (`:61`) → `asyncio.run` → processen dør.

Docker-restart-policyen starter den igen, workeren scanner samme tabel, finder samme række,
og dør igen. Rækken består, så loopet er permanent — ikke transient.

## Hvorfor det ikke bare er min probe

Det bærende er **ikke** at et fremmed `saga_type` kan komme ind i tabellen ved et uheld.
Det er at løkken **ikke har per-række-isolation**: én række workeren ikke forstår stopper
behandlingen af *alle* de andre. Den realistiske trigger er en refactor:

- en saga-type omdøbes eller fjernes fra registry'et, mens der stadig ligger aktive rækker
  med det gamle navn — en ganske almindelig migration
- en rollback til et image hvis registry ikke kender en saga-type der blev tilføjet efter

I begge tilfælde er konsekvensen ikke "den ene saga håndteres ikke", men **timeout-håndtering
falder helt ud for hele systemet**. Sagaer der hænger bliver aldrig kompenseret, og det er
netop den fejlklasse workeren findes for at dække.

Fejlmoden er desuden den ubehagelige slags: `saga-service`s API-proces er upåvirket og
`healthy`, de tre andre saga-workers kører, og der er ingen alarm på "timeouts håndteres ikke
længere". Kun `compose-state-check` (P2-38) ser den — og den fandt den faktisk her, hvilket er
gaten der gør sit arbejde.

## Foreslået retning (ikke besluttet)

Per-række `try/except UnknownSagaType` med en `logger.error` og `continue`, så én uforståelig
række degraderer til én sprunget række frem for et dødt worker-loop. Det er samme form som
CLAUDE.md's anti-pattern "try/except der sluger fejl uden logging", bare vendt om: her er
problemet en *ufanget* fejl der dræber processen, og fixet skal fange den **med** en loglinje —
ikke uden.

Åbent spørgsmål der ikke skal afgøres i P3-59: skal en sådan række markeres i DB'en (fx
`status='failed'` + `error_detail`), så den ikke scannes igen ved hver runde? Ellers logger
workeren den samme linje hvert 30. sekund for evigt, og vi har byttet et crash-loop for et
log-spam-loop.

## Ikke undersøgt

- Om `saga-command-consumer` og de to andre workers har samme uisolerede løkke. Sandsynligt,
  men ikke målt — antag det ikke.
- Om `find_stale_ids` kunne filtrere på kendte `saga_type`-værdier i SQL'en i stedet. Det
  flytter problemet til et sted hvor det er tavst, hvilket formentlig er værre.
