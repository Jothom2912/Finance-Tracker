---
date: 2026-07-27
topic: P1-15 + P2-26 (categorize-auth, nøglerotation, require_exp) og dev-notes gjort maskin-checkbar
---

# Session 2026-07-27 (midt på dagen) — P1-15/P2-26 + notes-infrastruktur

Dagens anden af tre sessioner (før [P3-40](2026-07-27-p340-worker-image-sharing.md) og
[P2-31](2026-07-27-p231-typecheck-gate.md)). Selve arbejdets forløb — fire påstande der ikke
holdt ved verifikation, to ting planen ikke forudså, to pre-eksisterende fund — står i
[planens Outcome](../plans/2026-07-27-p115-categorize-auth-and-secret-rotation.md#outcome) og
gentages **ikke** her. Denne log findes for det andet spor, som ingen plan dækker.

## Done

**P1-15 + P2-26** (CI-run `30266231499` på `4ce958b3`, 18/18):
`0a9eeb83`+`13e9147f`+`d4874bd0` (X-Internal-API-Key på `/api/v1/categorize`),
`34ac7c3b`+`9de527e9` (HS256-nøgle + `secrets.yaml` ud af trackede filer),
`72189b21`+`ece2918d` (`exp` håndhævet i alle 12 services), `6bdd70e8` (fail-closed på
`INTERNAL_API_KEY` i goal/banking/notification), `f71ef50e`+`e920aaa6` (to pre-eksisterende
fund rettet), `6489c89a` (`make test-e2e` kørbar lokalt).

**Notes-infrastruktur** — samme session, eget spor:
- `3024d6c9` — `make notes-check` + pre-commit-gate på dev-notes-drift.
- `c6f71e0e` — **STATUS.md indført**, ID'et gjort til opslagsnøgle, læsningen scoped.
- `dd8fdcca` — indexets hooks kortet ned; session-logs flyttet til `00-SESSIONS.md`.
- `5a1d9fe9` — lange BACKLOG-tabelceller flyttet til ID-adresserbare detail-sektioner.
- `2a7a437e` — død fil, index-drift og en skill-reference til intet ryddet.
- `5011acfa` (P3-39) + `ec39964a` (P3-40) — to fund rejst som items.

## Learned / surprised

- **"Afsender før håndhæver" holdt to gange, ikke kun én.** Rækkefølgen A1→A2 var planlagt;
  at syv testfiler mintede tokens uden `exp` og derfor måtte rettes *før* services krævede det
  (C1a→C1b) var samme form, opdaget undervejs. Værd at generalisere: **enhver håndhævelse har
  en afsenderside, og testene er også en afsender.**
- **En option-nøgle stavet forkert fejler tavst.** Planen foreskrev
  `options={"require_exp": True}` til analytics — det er *jose*-stavemåden, og analytics bruger
  PyJWT, som ignorerer ukendte options-nøgler uden at sige noget. Verificeret empirisk at et
  token uden `exp` slap igennem. Korrekt er `options={"require": ["exp"]}`. Der står nu en
  kommentar ved kaldet, netop fordi afvigelsen fra de 11 andre services inviterer til at blive
  "rettet" tilbage.
- **Den farligste konfigurationsfejl var den der kun rammer i produktion.**
  banking-sync-scheduleren satte aldrig `INTERNAL_API_KEY` og kørte på dev-defaulten, så efter
  rotationen sendte den en nøgle account-service ikke længere accepterede. Usynlig i test, fordi
  scheduleren først rører account-service når der findes en **rigtig** bankforbindelse. Det er
  den stærkeste begrundelse for fail-closed-fasen der findes — og den stod ikke i planen.
- **Notes-sporet var en reaktion på det samme mønster som dagens andre to items.** `notes-check`
  blev skrevet fordi index-drift og en skill-reference til intet havde ligget usynligt: en
  dokumentationsfejl der ikke kan blive rød opdages ikke. Samme form som P3-40's stale image og
  P2-31's manglende typecheck. Bemærk grænsen: `notes-check` verificerer **mekanik** (fil
  indekseret, frontmatter til stede), ikke om indholdet er sandt — og det er præcis den slags
  drift der ramte STATUS.md ved dagens slutning.

## Open ends

- **P2-15** (SOPS/secretGenerator) og **P1-08**'s historik-omskrivning — bevidst uden for scope.
- **Rotation gør ikke den gamle værdi u-disclosed.** Den har ligget i et offentligt repos
  historik; sessionen skiftede værdien og sikrede at den nye ikke committes.
- **analytics-service er stadig ikke på `shared/auth`** — valgt one-liner frem for migrering;
  konsolideringen er ortogonal og hører i eget item.
- **`notes-check` dækker ikke sandhedsværdi.** Overvej en check for de tilstande der faktisk
  gled: en plan med `status: done` uden `## Outcome`, og et shippet item uden session-log.
  Begge ville have fanget dagens efterslæb mekanisk.

## Notes updated

- Ny: denne log (skrevet 2026-07-28, efterslæb).
- Opdateret ved lukning: `plans/2026-07-27-p115-categorize-auth-and-secret-rotation.md`
  (Outcome), `backlog/BACKLOG.md` (P1-15, P2-26 done), findings
  `2026-07-26-categorize-endpoint-unauthenticated.md`,
  `2026-07-27-gateway-default-account-307.md`,
  `2026-07-27-e2e-alert-categorization-race.md` (alle resolved).
