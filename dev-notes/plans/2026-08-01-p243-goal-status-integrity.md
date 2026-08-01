---
title: "P2-43: goal-status validering og databaseinvariant"
date: 2026-08-01
status: done
backlog: [P2-43]
related:
  - ../architecture/services/account-budget-goal-services.md
  - ../findings/2026-07-27-goal-entity-two-runtime-types.md
  - 2026-07-31-p359-request-path-logging.md
---

# P2-43: goal-status validering og databaseinvariant

## Goal

En klient må ikke kunne persistere en goal-status, som gør create/update-svaret eller senere
læsninger til 500. API'et skal afvise andre lagrede værdier end `active` og `paused` med 422,
og databasen skal være sidste værn mod ugyldige writes. Færdig når den dokumenterede
`{"status": "bogus"}`-request afvises uden repository-, outbox- eller commit-kald, eksisterende
ugyldige rækker repareres deterministisk ved migration, og en direkte ugyldig SQL-write
afvises af constrainten.

## Context

[P2-43](../backlog/BACKLOG.md) blev fundet under
[P3-59](2026-07-31-p359-request-path-logging.md#items-der-spawnes-ikke-løses-her):
`GoalBase.status` er en fri streng, mens `GoalResponse.status` valideres som `GoalStatus`.
Servicen committer derfor først en ugyldig værdi og fejler derefter i `_to_dto`; alle senere
læsninger af rækken fejler på samme måde.

Repoets faktiske semantik har to forskellige begreber. Kun `active` og `paused` gemmes og kan
vælges i frontendens redigeringsformular; `completed` og `expired` beregnes som
`effective_status` ud fra beløb, dato og den gemte pause-status. En read-only optælling i den
lokale Postgres 2026-08-01 viste 33 `active`-rækker og ingen andre værdier. Migrationen skal
alligevel håndtere andre miljøer uden at antage, at de er rene.

## Non-goals

- Løs ikke hele P2-34: `float`/`Decimal`, repositoryernes to runtime-typer og den generelle
  domain-entity-typing forbliver særskilt arbejde.
- Gør ikke `completed` eller `expired` skrivbare; de forbliver beregnede visningstilstande.
- Ændr ikke goal-ruternes ejerskabs-, soft-delete-, default-goal- eller outboxadfærd.
- Tilføj ikke frontendændringer; den sender allerede kun `active`/`paused` og skelner mellem
  gemt `status` og beregnet `effective_status`.

## Steps

1. [x] Indfør en eksplicit gemt status-type med `active`/`paused` i
   `app/domain/entities.py`, og brug den på request-feltet i `app/application/dto.py` med
   `active` som default. Bevar den eksisterende fireværdige `GoalStatus` til responses og
   `effective_status`, så den offentlige læsekontrakt ikke ændres.
2. [x] Tilføj Alembic-migration `006` og matchende SQLAlchemy-metadata i `app/models.py`:
   normalisér `NULL` og værdier uden for `active|paused` til `active`, gør kolonnen
   `NOT NULL`, giv interne inserts samme `active`-default som API'et, og tilføj en navngivet
   check constraint. Downgrade fjerner constraint/default og genskaber nullable-kolonnen, men
   forsøger ikke at genopfinde de reparerede ugyldige værdier.
3. [x] Udvid `tests/unit/test_goal_api.py` med create- og update-negative kontroller, der
   forventer 422 for `bogus` og beviser, at service-metoden ikke kaldes; dæk også at manglende
   status normaliseres til `active`. Bevar positive kontroller for `active` og `paused` samt
   responseværdierne `completed`/`expired`.
4. [x] Tilføj en fokuseret migrationstest under `tests/migrations/`, som starter ved revision
   `005`, indsætter `NULL`, `bogus`, `completed`, `expired`, `active` og `paused`, upgrader til
   `006`, beviser den dokumenterede oprydning og beviser at en efterfølgende direkte ugyldig
   write afvises. Verificér også downgrade/upgrade-rundturen mod den tiltænkte Postgres-schema,
   ikke kun SQLite eller en Alembic-exitkode.
5. [x] Kør `make -C services/goal-service test` og
   `make -C services/goal-service check`. Rebuild/start `goal-service`, `goal-outbox-worker`
   og `goal-budget-consumer`, inspicér deres logs, verificér `alembic current` = `006`, og kør
   en API-negativ kontrol hvor `PUT /api/v1/goals/{id}` med `bogus` giver 422 og den
   efterfølgende GET fortsat returnerer den uændrede række. Kør til sidst `make notes-check`.

## Risks & rollback

Den væsentligste risiko er at forveksle beregnet `completed`/`expired` med legitim lagret
status. Det opdages ved migrationstesten og ved response-tests, som fortsat kræver begge
effective-statusværdier samtidig med, at de normaliseres til `active` som lagret værdi.
Normalisering til `active` er bevidst: en ukendt værdi kan ikke fortolkes sikkert, mens
`active` matcher servicens nuværende fallback for `NULL` og ukendte værdier i
`effective_status`.

Rollback er kode-rollback plus Alembic downgrade fra `006`; det genåbner kolonnen for gamle
klienter, men de værdier migrationen reparerede kan ikke genskabes. Før migration i et delt
miljø skal antal og værdier derfor logges/backup'es, og efter migration skal constraint,
revision og statusfordeling kontrolleres eksplicit.

## Outcome (fill in when done)

Shippet 2026-08-01 i goal-service. Request-DTO'en bruger nu `StoredGoalStatus`, så kun
`active`/`paused` accepteres og manglende status bliver `active`; den eksisterende
`GoalStatus`-response beholder de beregnede `completed`/`expired`. Migration `006` reparerer
`NULL` og alle andre lagrede værdier til `active`, tilføjer `NOT NULL`, server-default og
`ck_goals_status_stored`. Server-defaulten blev tilføjet under implementeringen, fordi den
fulde suite viste, at legitime interne test-/repository-writes udelader status; den bevarer
samme fallbackadfærd uden at svække constrainten.

Verifikation: `make -C services/goal-service test` grøn med 125 tests; `make ... check` grøn;
fokuseret migration/API-suite 14 tests grøn; `make notes-check` grøn. Det genbyggede image
startede API, outbox-worker og budget-month-closed-consumer uden fejl. Lokal Postgres migrerede
fra `005` til `006 (head)`, beholdt 33 `active`-rækker og eksponerer den navngivne constraint.
En isoleret Postgres-database bestod desuden `upgrade 006 → downgrade 005 → upgrade 006` og
blev fjernet efter kontrollen; slutskemaet havde `NOT NULL`, `'active'`-default og én constraint.
En rigtig PUT mod mål 15 med `bogus` gav 422 mellem to identiske 200-GET-svar. En direkte SQL
UPDATE til `bogus` blev afvist af constrainten, og rækken forblev `active`.
