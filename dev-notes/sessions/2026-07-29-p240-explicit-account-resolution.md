---
date: 2026-07-29
topic: P2-40 — gateway'ens accounts[0]-fallback, og den tokonto-fixture der kan se den
backlog: [P2-40]
---

# Session 2026-07-29 — P2-40: vælg kontoen eksplicit, eller fejl ærligt

## Done

- **`ad0b8d54` — fixet + de fem tests der bærer det.** `get_account_id_from_headers` opløser
  `name == "Default Account"` eksplicit når `X-Account-ID` mangler, og returnerer `None` +
  en WARNING med `user_id` frem for at gætte. Gateway havde **ingen** test af `auth.py` før nu;
  account-service mockes med `httpx.MockTransport`, ikke `MagicMock` (P3-41).
- **`6050aeb8` — tokonto-fixturen i browser-laget.** `twoAccountSession` +
  `accountScopedPage` + `e2e/dashboard-scopes-to-selected-account.spec.js`. Fjernede samtidig
  `?? accounts[0]`-halen fra fixturens konto-opløsning: samme fejl som gateway'ens.
- **Docs:** planens Outcome, finding'en → `resolved`, STATUS.md, BACKLOG.md (P2-40 done +
  detail-sektion), 00-INDEX, og to nye items — **P3-48** (frontend-vagt) og **P3-49**
  (`make security` vs. CI's bandit).

Verifikation: gateway 28 passed (23 før), browser 4 passed, `test-e2e` 24 passed, `lint-repo`
og `compose-check` grønne, `notes-check` 137 notes uden problemer.

## Learned / surprised

1. **Den naive reproduktion viser ikke fejlen — og planen foreskrev den naive.** Planens trin 1
   sagde "opret en anden konto, læg data på den". Det gav 0,0 både med og uden header, fordi
   sagaen skaber `Default Account` *først*, så `accounts[0]` **er** defaultkontoen og fallbacken
   svarer rigtigt ved et tilfælde. Fejlen kræver at defaultkontoen er en senere række, og appen
   kan selv skabe den tilstand: omdøb saga-kontoen (det frigør `one_default_per_user`-pladsen),
   opret så en ny `Default Account`. **Da faldt tallet ud: 1554,0 kr. fra den forkerte konto,
   uden en fejl** — mod 0,0 efter fixet. Uden det ekstra trin havde jeg haft en grøn baseline
   og ingen diskriminator, altså præcis den grøn-på-ingenting itemet handler om.
2. **Et negativt resultat, og det er noteret som et.** Planens Context påstod at appens egen
   `budget_start_day`-`PUT` kan flytte hvilken konto der er `accounts[0]`. Tre listekald med en
   `PUT` imellem: samme rækkefølge hver gang. Instrumentets grænse hører med (to rækker, og en
   small-field-update kan Postgres sandsynligvis lave HOT/in-page). Fejlen behøvede ikke
   *ustabil* rækkefølge — kun **uspecificeret**.
3. **En fejlbesked der gætter, sender diagnosen væk fra årsagen.** Browser-suiten fejlede med
   **502**, men fixturens fejltekst nævnte 429 og rate-limit-zonen *ubetinget*, så det første
   minut gik i nginx.conf. Årsagen var **P3-45**, som allerede står i backloggen: nginx cacher
   upstream-IP'er fra config-load, og mit `compose up --build gateway-service` havde genskabt
   user-service. `docker compose restart frontend` var fixet. Fælden var altså ikke ny — det nye
   er at *vores egen diagnostik pegede væk fra et item vi selv har skrevet*. Hintet er nu
   betinget af statuskoden og navngiver P3-45.
4. **Kontrollens bærende detalje er hvilken konto der er den valgte.** I den nye spec er det den
   **anden**, ikke standardkontoen. Havde standardkontoen været den valgte, ville en server der
   ignorerer `X-Account-ID` og falder tilbage til standardkontoen svare rigtigt ved et tilfælde,
   og kontrollen ville være grøn igen — præcis P2-39's fejl, gentaget et lag højere oppe. Med
   samme mutation som P2-39: **1 failed** (kortet viste standardkontoens `10.449,74` hvor
   `2.718,28` skulle stå), de tre øvrige browser-specs grønne, `npm test` 346 passed.
5. **Testen fejlede først på sit eget prædikat, ikke på produktet.** Den ventede på
   `totalExpenses == 9111.99` for standardkontoen og fik `10449.74` — vores beløb plus
   `dashboard-loads-real-data`s 1337,75, fordi de to specs deler bruger og standardkonto i samme
   worker. Rettet til en delta-måling. Værd at huske: en worker-scoped fixture er *delt tilstand*,
   og en eksakt total over delt tilstand er ikke et stabilt prædikat.
6. **`make check` var rød på gateway før jeg rørte den.** `make security` mangler CI's
   `-ll -ii`, så et Low-fund (`B105`, `token = ""`) fælder den lokalt og ikke i CI. Verificeret
   ved at køre bandit på `auth.py` fra før fix-commit'en: samme rc, samme linje. → P3-49.
7. **`prettier` er ikke et værktøj i dette repo.** Ingen config, ikke i `package.json`, og
   `npm run lint` dækker kun `src/` — ikke `e2e/`. Et reflex-agtigt `npx prettier --write`
   omformaterede to filer til dobbelte anførselstegn og 80 kolonner og måtte rulles tilbage.
8. **Planens `make -C services/gateway-service typecheck` findes ikke.** Gateway har hverken
   mypy-target eller mypy-dependency (den er en af de tre uden for gaten). Aflæsningen blev en
   manuel gennemgang i stedet.

## Open ends

- **P3-48 er den der bør følge tæt efter.** Fixet gør serveren ærlig, men en bruger der når
  `/dashboard` uden valgt konto ser nu en GraphQL-fejl frem for forkerte tal. Korrekt, og en
  dårligere skærm. Otte ruter i blast radius, og `CategoriesPage.jsx:29` har allerede en ad-hoc
  variant at konsolidere.
- **CI er ikke aflæst for disse commits endnu** — intet er pushet. Næste skridt er push +
  `make ci-status`.
- **Dev-stakken har fået tre brugere mere** (427, 428 plus en probe) med konti 430–433, hvoraf
  432/433 er omdøbt til 'Gammel Konto'/'Ikke Default'. De kan ikke ryddes: der findes ingen
  sletningssti (**P2-41**). Nævnes her fordi 428 er en flerkonto-bruger *uden* defaultkonto,
  altså en nyttig fixture for P3-48 — og en fælde for enhver der antager at hver bruger har én.
- **Om account-service bør sortere sit listesvar** er stadig ubesvaret. Målingen gjorde
  spørgsmålet mindre, ikke større, men `AccountSelector`s liste er også usorteret for brugeren.

## Notes updated

- `plans/2026-07-28-p240-gateway-explicit-account-resolution.md` — Outcome, `status: done`
- `findings/2026-07-28-gateway-falls-back-to-first-account.md` — `resolved` + `resolved-by`,
  den reproduktion der faktisk virker, og det negative resultat
- `STATUS.md`, `backlog/BACKLOG.md` (P2-40 done + detail; P3-48, P3-49 nye), `00-INDEX.md`
- denne log + `sessions/00-SESSIONS.md`
