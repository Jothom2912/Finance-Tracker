---
title: "Budget-alert e2e-suiten var flaky på to races — begge fordi den ventede på det forkerte read-model"
date: 2026-07-27
severity: MEDIUM
area: test
status: resolved
resolved-by: e920aaa6
---

# Budget-alert e2e-suiten ventede på det forkerte read-model — to gange

`tests/e2e/test_budget_threshold_alert_e2e.py` fejlede intermitterende: 1 af 3
kørsler, med 2-3 røde tests. Den var grøn nok til at se stabil ud og rød nok til
at maskere en rigtig regression. To uafhængige årsager, samme grundfejl.

## Race 1 — kategoriseringen

**Defekt**: seed-beskrivelserne var `"E2E 0"`, `"E2E 1"`, `"E2E over"`. De matcher
ingen regel, ingen ML-model og ingen LLM, så pipelinen løb tør for tiers og faldt
til fallback:

```
WARNING  All tiers exhausted for 'E2E 0'. Using fallback.
INFO     Categorized transaction 1249 -> cat=8, sub=32, tier=fallback [low]
```

Fallback er **deterministisk** — den lander altid i "Diverse" (8). Så pipelinen
omskrev *altid* rækkerne væk fra den kategori testen oprettede dem med.

Fixturens barriere hed `_await_stable_category` og krævede "to identiske
læsninger 2 sekunder fra hinanden". Det er et gæt, ikke et hegn. Var korrektionen
langsom, så fixturen create-time-kategorien to gange, konkluderede "stabil",
lagde budgetlinjen der — og bagefter flyttede forbruget til 8. Budgetlinjen og
forbruget pegede så på hver sin kategori, og per-linje-alarmen kunne aldrig fyre.

**Rettelse**: beskrivelserne bærer nu et globalt keyword (`REMA1000` →
`Mad & drikke`), så regel-tieren afgør kategorien og create-time-værdien er den
samme som udfaldet. Barrieren venter nu på et *forventet* svar og fejler på et
forkert, i stedet for at gætte på stabilitet.

## Race 2 — analytics-read-siden

**Defekt**: efter race 1 var lukket fejlede suiten stadig. Tick'et rapporterede
`failed_upstream: 0` og emitterede ingenting.

Scheduleren læser ikke transaktioner. Den læser `expenses_by_category` fra
analytics' overview-endpoint (P1-13,
[decisions/2026-07-25-budget-spend-from-analytics.md](../decisions/2026-07-25-budget-spend-from-analytics.md)).
Analytics er en Elasticsearch-read-side med sin egen projection-consumer og
dermed et ukendt lag bag transaction-DB'en.

Testen ventede på `postgres-transactions` og tickede så. Fra analytics' synspunkt
var pengene ikke brugt endnu, så der var intet tærskel-overløb at emittere. Ingen
fejl nogen steder — bare et tick der korrekt konkluderede "ingenting at gøre".

**Rettelse**: en barriere der poller præcis den kilde scheduleren læser, før der
tickes.

## Lære

Begge races er samme fejl: **barrieren ventede på et andet read-model end det
system-under-test læser.** I en CQRS-arkitektur med flere read-sider er
"transaktionen findes i DB'en" ikke det samme som "forbruget er synligt for den
komponent jeg er ved at trigge".

Og `failed_upstream: 0` er ikke et sundhedstegn — det betød her "jeg spurgte, og
svaret var nul". Et tick der ikke finder noget ser identisk ud med et tick hvis
input ikke er ankommet endnu. Samme klasse som
[[project_exam_note_event_delivery]]: en grøn live-verifikation kan selv være
falsk.

Efter rettelsen: 24/24 fire kørsler i træk.
