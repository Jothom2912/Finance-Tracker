---
title: "F2-07: sammenhængende budgetstatus og kategoriperiode"
date: 2026-08-01
status: done
backlog: [F2-07]
related:
  - ../patterns/frontend-data-patterns.md
  - ../architecture/services/frontend.md
---

# F2-07: sammenhængende budgetstatus og kategoriperiode

## Goal

Dashboardets budgetadvarsel skal navngive hver overskredet kategori og linke til samme kategori
i samme budgetperiode på kategorisiden. Kategorisidens forbrug og budget skal bruge ét fælles
periodebegreb. Færdig når august for en konto med startdag 26 viser udgifter fra
26. juli–25. august på både dashboard og kategoriside, og et klik på fx "Transport — 500 kr.
over budget" åbner august med Transport valgt.

## Context

Brugerrapporten 2026-08-01 nævnte manglende løn, overførsel og SU ved månedsskiftet samt en
utydelig over-budget-visning. Read-only kontrol af den aktuelle lokale stak viste, at konto 1
har `budget_start_day=26`, og at `LØNOVERFØRSEL` på 3.348 kr. og `SU` på 6.443 kr. fra 31. juli
findes både i transaction-service og analytics-projektionen for budgetperioden
2026-07-26–2026-08-25. Analytics summerer ni indtægtsposter til 13.717 kr. i perioden. Den
kanoniske aggregation er altså korrekt; præsentationen gør periodens grænser og indtægternes
placering for lette at misforstå.

Den efterfølgende afklaring indsnævrede dashboard-problemet: summerne og den eksisterende
periodetekst fungerer acceptabelt; den konkrete mangel er advarslen "1 kategori over budget",
som ikke siger hvilken kategori det er.

Der er samtidig en reel periodedrift på kategorisiden. `usePeriodOverview.jsx` kalder
`financialOverview(startDate, endDate)` med kalenderintervallet 1.–sidste dag, men kalder
`budgetSummary(month, year)` med kontoens budgetperiode. For konto 1 kan august-siden derfor
vise nul udgifter fra 1.–31. august samtidig med et augustbudget, hvis udgifterne ligger
26.–31. juli. Gatewayens eksisterende `periodOverview(month, year)` løser allerede den samme
budgetperiode korrekt for dashboardet og skal genbruges her.

`CategoryFilterPanel` tilbyder desuden Udgifter, Indtægter, Overførsler og Alle, mens
`financialOverview`/`periodOverview` kun leverer `expensesByCategory`. `typeFilter` ændrer
derfor kun hvilke chips der vises; det ændrer ikke datasættet. Det er bedre at gøre denne side
ærligt udgifts- og budgetorienteret end at udvide analytics- og GraphQL-kontrakterne som en
sideeffekt af denne rettelse.

## Non-goals

- Ændr ikke dashboardets eksisterende periodeoverskrift eller budgetperiodens domæneregler;
  de målte indtægtsposter og summer er allerede korrekte.
- Opret ikke syntetiske transaktioner fra `planned_transactions`. Tabellen har kun CRUD og
  ingen scheduler/materialisering; forecast/recurrence hører fortsat til F2-01/F2-02.
- Ændr ikke bank-sync, kategorisering, budgetlinjer eller historiske data.
- Tilføj ikke indtægts-/overførsels-breakdowns eller en ny API-kontrakt. Det kan planlægges
  separat, hvis kategorisiden senere skal være et overblik over alle transaktionstyper.

## Steps

1. [x] Ret `usePeriodOverview.jsx` til at spørge gatewayens eksisterende
   `periodOverview(month, year)` i stedet for kalenderbaseret `financialOverview(startDate,
   endDate)`. Bevar query key, `budgetSummary` og boundary-normaliseringen, så eksisterende
   invalidation fortsat virker.
2. [x] Gør `CategoriesPage.jsx` og `CategoryFilterPanel.jsx` eksplicit udgifts-/budgetorienterede:
   fjern det ikke-fungerende typevalg, vis den faktiske `overview.startDate`–`endDate`, og lad
   kategori-chips være udgiftskategorier plus Ukategoriseret. Bevar multi-select og
   subkategori-drilldown.
3. [x] Tilføj valideret URL-state på kategorisiden (`month`, `year`, `category`): gyldige
   værdier initialiserer sidens eksisterende kontroller; ugyldige eller fremmede kategori-id'er
   ignoreres og falder tilbage til den aktuelle måned uden at blanke siden.
4. [x] Ret `BudgetProgressSection.jsx` til at udlede overskredne linjer fra
   `remainingAmount < 0`, navngive dem i advarslen med "X kr. over budget" og linke hver til
   `/categories?month=<budgetSummary.month>&year=<budgetSummary.year>&category=<id>`.
   Overskredne linjer må ikke kunne gemmes bag "Vis flere"; øvrige linjer beholder den
   eksisterende kompakte liste og sortering.
5. [x] Tilføj fokuserede Vitest/React Testing Library-tests for: GraphQL-queryens
   budgetperiodesemantik; konto-startdag 26 via et svar med 26. juli–25. august; URL-initiering
   og ugyldig fallback; korrekt kategori/periode i dashboardlinket; flere overskridelser; og
   negativ kontrol hvor `remainingAmount === 0` ikke markeres som overskredet.
6. [x] Verificér med `npm test -- --run` og `npm run build` i `services/frontend`. Kør en
   Playwright-flow mod den lokale stak: august-dashboard → navngivet budgetadvarsel → link →
   kategoriside med samme 26. juli–25. august-periode, valgt kategori og dens budgetstatus.

## Risks & rollback

Den største risiko er, at URL-state og lokal filter-state divergerer, eller at et gammelt link
med et slettet kategori-id giver et tomt overblik. Parse kun URL'en ved initialisering, validér
mod de hentede kategorier og brug "ingen kategorier valgt" som sikker all-expenses fallback.
En anden risiko er at kalde `remainingAmount < 0` over budget ét sted og
`percentageUsed > 100` et andet; begge sider skal bruge `remainingAmount < 0`, med
`remainingAmount === 0` som negativ kontrol. Ændringen kræver ingen server- eller
migrationsrollback; frontend-queryen kan rulles tilbage uafhængigt.

## Outcome (fill in when done)

Shippet 2026-08-01 som en ren frontendændring uden API- eller domæneændringer.
`usePeriodOverview` læser nu både kategoriudgifter og budget fra gatewayens budget-aware
`periodOverview`; kategorisiden viser intervallet, har kun de udgiftsfiltre dens data faktisk
understøtter og accepterer valideret `month`/`year`/`category` URL-state. Dashboardets
budgetadvarsel navngiver hver overskridelse, viser beløbet og linker til det samme udsnit;
overskridelser skjules aldrig af fem-linjers kollapset visning.

Verifikation: frontend lint grøn; produktionsbuild grøn (kun den eksisterende Vite-warning om
en bundle over 500 kB); 37 testfiler/350 tests grønne; Playwright mod det genbyggede image
5/5 grøn. Den positive deep-link-flow er deterministisk dækket i komponent- og sidetests,
inklusive 26. juli–25. august og ugyldig kategori-fallback. En ekstra read-only live-kontrol
på konto 1 kunne ikke følge en positiv advarsel, fordi kontoens aktuelle augustlinjer ikke
længere var over budget; den bekræftede dermed den negative tilstand (ingen falsk advarsel)
frem for den positive flow. Ingen testdata blev ændret for at fremprovokere en overskridelse.
