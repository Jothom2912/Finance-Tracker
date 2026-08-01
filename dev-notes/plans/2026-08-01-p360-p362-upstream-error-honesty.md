---
title: P3-60 + P3-62 — ærlige upstream-fejl og ét account-opslag ved måloprettelse
date: 2026-08-01
status: done
backlog: [P3-60, P3-62]
related:
  - 2026-07-31-p359-request-path-logging.md
  - ../architecture/services/account-budget-goal-services.md
  - ../architecture/services/frontend.md
---

# P3-60 + P3-62 — ærlige upstream-fejl og ét account-opslag ved måloprettelse

## Goal

En konto-oprettelse må kun svare 400 "brugeren findes ikke", når user-service entydigt svarer
404. Timeout, forbindelsesfejl, afvist intern nøgle og øvrige upstream-fejl skal svare 503 med en
midlertidig fejlbesked, som AccountSelector viser uden at genindsende mutationen automatisk.
Goal-service skal samtidig nøjes med det ene ejerskabsopslag, der allerede skelner 404 fra 503,
så måloprettelse ikke udfører et redundant andet HTTP-kald.

## Context

[P3-59](2026-07-31-p359-request-path-logging.md#items-der-spawnes-ikke-løses-her) gjorde
fejlformerne synlige, men ændrede bevidst ikke kontrakten. Verifikation mod den aktuelle kode
viser, at `account-service/app/adapters/outbound/user_adapter.py` stadig kollapser non-404 og
request-fejl forkert, mens goal-services nåelige `get_owner_user_id`-sti allerede svarer ærligt
med 404/503. Goal-halvdelen af P3-60 er derfor reelt [P3-62](../backlog/BACKLOG.md#p3-62): den
efterfølgende `exists()`-gren er død og bør fjernes frem for at få endnu en fejlkontrakt.

## Non-goals

- Ingen ændring af ægte "bruger findes ikke"-adfærd: user-services 404 forbliver account 400.
- Ingen automatisk retry af konto-oprettelse; mutations-retry forbliver 0 for at undgå dobbelte
  writes ved tvetydige transportsvar.
- Ingen generel standardisering af upstream-exceptions på tværs af alle services.
- Ingen ændring af account/goal-payloads, autentifikation, database eller events.
- Ingen oprydning af account-services øvrige gruppeopslag i `get_users_by_ids`; P3-60 ejer kun
  konto-oprettelsens `exists`-sti.

## Steps

1. [x] **Gør account-services port og adapter ærlige.** Tilføj en framework-uafhængig
   `UpstreamServiceUnavailable` i `app/domain/exceptions.py`; lad
   `app/adapters/outbound/user_adapter.py` returnere `False` kun på 404, returnere `True` på 200
   og rejse exceptionen på `httpx.RequestError`, alle øvrige statuskoder og en ubrugelig
   200-payload hvis kontrakten kræver det. Bevar lazy logging uden credentials eller hostile
   payloads.
2. [x] **Map kontrakten i inbound-adapteren.** Map exceptionen eksplicit til 503 i
   `app/adapters/inbound/account_api.py`; behold `UserNotFoundForAccount` → 400. Udvid unit- og
   integrationstests i `services/account-service/tests/` med 404-, 401/5xx- og request-error-
   negative controls og bevis, at repository-write ikke kaldes ved begge afvisningsklasser.
3. [x] **Fjern goal-services døde andet opslag.** Fjern `exists()` fra
   `app/application/ports/outbound.py`, `app/adapters/outbound/account_adapter.py` og kaldet i
   `app/application/service.py`; opdatér fakes/mocks og tests, så måloprettelse beviseligt laver
   ét owner-kald, stadig giver account-not-found på 404 og stadig propagaterer 503 før write.
4. [x] **Vis midlertidig fejl i AccountSelector.** I
   `services/frontend/src/pages/AccountSelector.jsx` skelnes `ApiError.status === 503` fra
   brugerfejl og vises som en handlingsorienteret midlertidig besked. Tilføj en fokuseret
   `AccountSelector.test.jsx`, der beviser 503-beskeden, bevaret formtilstand og præcis ét kald
   til `createAccount`; 400-detail forbliver uændret.
5. [x] **Verifikation.** Kør `make -C services/account-service test` og `check`,
   `make -C services/goal-service test` og `check`, samt `npm test -- --run
   src/pages/AccountSelector.test.jsx`, `npm run lint` og `npm run build` i frontenden. Kør
   derefter `make notes-check`. Hvis den lokale stack er tilgængelig, driv også en negativ
   request med user-service stoppet og bevis 503 + nul account-write; statiske tests alene må
   ikke omtales som live-bevis.

## Risks & rollback

Den primære risiko er, at eksisterende tests eller callers har kodet "enhver non-200 = findes
ikke" ind; 404-kontrollen opdager regression af den legitime gren, mens 401/5xx/request-error-
kontrollerne opdager fortsat kollaps. Fjernelsen af goal-`exists()` kan ramme test doubles mere
end produktion; et søg efter portens eneste callsites samt service-testen med `assert_awaited_once`
detekterer drift. Frontendens mutation genforsøges ikke, så der introduceres ingen dublet-write-
risiko. Ændringen kan rulles tilbage servicevis: restore goal-port/kaldet uden datamigration, og
restore account-adapterens gamle mapping; der er ingen persistent schema- eller eventændring.

## Outcome (fill in when done)

P3-60s reelle fejl er lukket i account-service: `UserServiceAdapter.exists()` returnerer nu kun
`False` på den entydige 404, mens request-fejl og 401/422/5xx logger diskriminanten og rejser en
framework-uafhængig `UpstreamServiceUnavailable`. Inbound-adapteren mapper den til 503;
integrationstesten beviser 503-detail og en tom konto-liste efter afvisningen, mens 404 stadig
giver den eksisterende 400.

P3-62 fjernede hele `exists()`-metoden fra goal-porten og HTTP-adapteren samt dens døde andet
kald. Måloprettelse bruger nu præcis ét `get_owner_user_id`-opslag; testene beviser både ét kald,
503 før write og bevaret account-not-found-semantik. Den daterede goal-README blev samtidig
rettet fra user-service til account-service.

AccountSelector viser en handlingsorienteret midlertidig besked på 503, bevarer inputtet og
kalder kun `createAccount` én gang; 400-detail vises fortsat uændret. Produktionskonfigurationens
`mutations.retry: 0` er urørt.

Verifikation 2026-08-01:

- `make -C services/account-service check` via et midlertidigt miljø: **46 passed**, ruff,
  format og bandit grønne. Account-service er repoets dokumenterede requirements.txt-undtagelse
  og havde intet lokalt pytest-miljø.
- `make -C services/goal-service test check`: **118 passed**, ruff/format grønne.
- Frontend `npm test`, `npm run lint`, `npm run build`: **352 passed**, lint og build grønne;
  Vitest har eksisterende React `act(...)`-warnings, og Vite har den kendte >500 kB chunk-warning.
- Live-smoke efter `docker compose up -d --build --wait account-service goal-service frontend`:
  alle berørte services blev healthy med rene startup-logs. Et lokalt signeret JWT for en frisk,
  uregistreret bruger gav konto-listelængde **0**; med user-service stoppet gav
  `POST /api/v1/accounts/` præcis **503** og detail
  `user-service er midlertidigt utilgængelig.`; den efterfølgende konto-liste var stadig **0**.
  Account-loggen bar `ConnectError`, bruger-id og access-linjens 503. En `finally`-blok startede
  user-service igen, og dens `/health` svarede 200.
- `make compose-state-check`: **62 containere**, ingen dead, exited nonzero eller restarting;
  kun de ti forventede migration/one-shot-containere exited cleanly.
- `make notes-check` og `git diff --check`: grønne ved afsluttende verifikation.
