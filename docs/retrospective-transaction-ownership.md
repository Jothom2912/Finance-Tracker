# Retrospective: Transaction Ownership Migration

**Dato:** 16. april 2026
**Scope:** M1 → M4 + M3.5 — fem commits, fire dages arbejde
**Commits:** `1d2a12a`, `47e2de5`, `513a3ba`, `e846b92`, `433dbfd`

---

## 1. Hvad var den oprindelige smerte?

Transaction CRUD fandtes i **to parallelle implementeringer** — i monolithen (MySQL, hexagonal) og i transaction-service (PostgreSQL, hexagonal). Oven i det skrev banking-modulet bank-synkede transaktioner **direkte til MySQL**, som en tredje skrivesti der slet ikke involverede transaction-service. Konsekvensen var en stille split-brain: transaktioner oprettet via frontend → transaction-service (PostgreSQL) **dukkede ikke op i dashboardet**, fordi dashboardet læste fra MySQL.

Det var ikke en bug i den klassiske forstand — koden fejlede ikke. Det var en regression i **datasammenhæng**, og det blev først synligt når man sammenlignede to visninger.

## 2. Hvad var den centrale arkitekturelle indsigt?

**Invariants live with the aggregate that owns them.**

Da jeg skulle forklare hvorfor dedup hørte hjemme i transaction-service og ikke i banking, fandt jeg det argument der gjorde resten af migrationen logisk: "ingen duplikater" er et invariant på transaction-aggregate'et. Banking er blot én af potentielt mange producenter (CSV, manuel indtastning, mobile app, nye bank-integrationer). Hvis invarianten bor hos producenten, skal den re-implementeres for hver ny kilde og håndhæves på tværs af distribuerede read-before-write tjek. Hvis den bor hos aggregate-ejeren, defineres den én gang og er automatisk atomart håndhævet i ejerens database.

Det samme argument drev M3.5 (kategoriserings-metadata hører til transaktionen, ikke til den der oprettede den) og M4 (projection-tabeller er read-only fordi deres invariants ejes et andet sted).

## 3. Hvilken beslutning var sværest?

**M3.5 — var det unfinished business eller var det cleanup?**

Efter M3 havde jeg skrevet en "kendt begrænsning" om at `categorization_tier`, `subcategory_id` og `categorization_confidence` ikke propagerede til PostgreSQL. Jeg kaldte det "cleanup" fordi jeg gerne ville afslutte arbejdet som komplet. Feedback presenterede mig for at det var en **data-completeness regression**, ikke kosmetik — tier-badges er feedback-loopet for rule engine, og at lade dem gå i sort er at lade et signal dø.

Svaret var at indsætte M3.5 som et separat skridt. Ærlig klassificering af regression vs. cleanup er sværere end det lyder fordi der er en impulse mod at ville lukke historien. Man skal insistere på at forsinket er OK hvis det betyder *komplet*.

## 4. Hvad ville jeg gøre anderledes?

**M3.5 burde have været del af M3 fra starten.**

Da jeg planlagde M3 talte jeg mig fra Alembic-migrationen fordi den "føltes som scope creep". Men HTTP-klienten og schema-udvidelsen er samme arkitektoniske ændring set fra to sider: den ene flytter skrivestien, den anden flytter datamodellen med. Jeg har lært at mistro en plan der siger "vi gør X nu og sikrer os at vi ikke mister data senere" — det er ofte to sætninger der burde være én.

Den anden ting er at M2 havde lækage. Jeg efterlod dead write-kode i Category-siden fordi jeg antog at når der ingen router-registrering var, var koden uskadelig. Det var først fitness-testen i M4 der opfangede det. Næste gang: kør fitness-testen **mens** jeg rydder op, ikke bagefter.

## 5. Hvad er det ene mønster jeg vil tage med til næste projekt?

**AST-baseret architecture fitness test med aliasanalyse.**

Reglen ser lille ud: "flag konstruktør-kald af navne importeret fra `backend.models.mysql.*`". Men den gør noget vigtigt — den kobler **dokumentation, håndhævelse og feedback-loop** sammen:

- Docstringen på modellen siger "read-only"
- `info={"read_only": True}`-markøren siger det til SQLAlchemy
- Fitness-testen opfanger overtrædelser på min maskine i 90ms
- Og positive control (`test_projection_markers_present`) sikrer at dokumentationen ikke kan fjernes uden at regler også fejler

Det er den eneste form for arkitektur-håndhævelse jeg har mødt hvor **fejlen kommer tidligt nok til at være billig**, uden at drukne i runtime-kompleksitet. Og den betalte sig selv den dag jeg skrev den ved at finde en ægte bug første gang den kørte.

---

## Nøgletal

| Metric | Værdi |
|--------|-------|
| Kode fjernet, netto | −2968 linjer (M2 alene) |
| Test suite hastighed | 4 min → 4.6s (110× hurtigere) |
| Nye tests tilføjet | +22 på tværs af monolith + transaction-service |
| Dead tests fjernet | 38 |
| Parallelle skrivestier til transaktioner | 3 → 1 |
| Bugs opfanget af M4 fitness-test | 1 (dead split-brain-risiko i Category) |

## Det ene resumé

> Jeg flyttede transaktionsskrivninger fra tre parallelle stier til én ejer, berigede events til at bære det fulde projection-datasæt, og låste invarianten fast med en statisk fitness-test der fandt en bug første gang den kørte. Netto −2968 linjer kode, test-suite 110× hurtigere, nul regressioner.
