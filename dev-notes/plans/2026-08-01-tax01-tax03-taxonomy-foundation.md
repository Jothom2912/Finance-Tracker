---
title: TAX-01–03 — taxonomy foundation
date: 2026-08-01
status: done
backlog: [TAX-01, TAX-02, TAX-03]
related:
  - ../backlog/TAXONOMY-OPTIMIZATION.md
  - ../backlog/ML-CATEGORIZATION.md
  - ../architecture/services/categorization-and-ai-services.md
  - ../decisions/2026-08-01-taxonomy-semantics-and-identity.md
  - ../../docs/ADR-003-taxonomy-ownership-consolidated.md
---

# TAX-01–03 — taxonomy foundation

## Goal

Agree a stable Danish personal-finance taxonomy before changing production data: an approved
category matrix with explicit boundaries, stable semantic keys and lifecycle rules, plus a
complete mapping for every current category and subcategory. Completion means all 10 current
categories and 41 current subcategories have exactly one reviewed disposition, downstream
impact is documented, and TAX-04–09 can be planned without relying on mutable display names.

## Context

The current taxonomy and seed rules mix semantic definitions, merchant aliases and matching
rules in `services/categorization-service/app/domain/taxonomy.py`. The verified baseline and
candidate target are in the [taxonomy roadmap](../backlog/TAXONOMY-OPTIMIZATION.md). The
categorization service is the sole writer, while transaction-service and analytics hold
event-synced, denormalized read copies. Budgets and existing transactions therefore make even a
seemingly simple rename or move a cross-service data decision.

This plan deliberately settles TAX-01–03 before ML labels are frozen or migrations are written.
It has a product-review checkpoint because several boundaries cannot be inferred safely from
code alone.

## Non-goals

- No schema, domain-model, API, event-contract or migration changes.
- No edits to the existing seed taxonomy or the 130 merchant mappings.
- No writes, bulk recategorization or repair against existing user transactions or budgets.
- No per-user custom categories, LLM categorization, trip/project dimension or receipt detail.
- No implementation of TAX-04–09; those receive separate plans after this foundation is approved.

## Steps

1. [x] **Freeze the verified baseline.** Inspect the live domain seed, additive migrations and
   taxonomy consumers in categorization-, transaction-, analytics- and budget-service. Add a
   deterministic audit/test helper under `services/categorization-service/tests/` that reports
   the 10/41 nodes, pinned IDs, category types, fallbacks and seed-rule targets, and fails on
   duplicate names or orphaned rule targets. This is read-only with respect to application data.
2. [x] **Complete TAX-01 definitions.** Turn the roadmap candidate into a reviewable matrix in
   this plan (or a directly linked canonical taxonomy note): stable proposed key, Danish display
   name, type, definition, inclusions, exclusions, fallback and representative examples for each
   node. Resolve investment, loan principal/interest, refunds, MobilePay, cash withdrawal,
   travel, subscriptions and internal-transfer evidence explicitly. Keep the target near 12–15
   parents and 50–70 children unless the review records why a boundary earns a different shape.
3. [x] **Product review checkpoint — stop for approval.** Review the matrix and boundary examples
   with the product owner. Record approved choices and rejected alternatives with
   `dev-notes-decision`; do not continue to identity/mapping on unresolved semantics.
4. [x] **Complete TAX-02 identity and lifecycle design.** Specify immutable ASCII semantic keys,
   display-name rename behavior, parent/child key rules, typed fallbacks, taxonomy versioning,
   and deprecate/merge semantics. Verify that identifiers remain the grouping keys for budgets,
   analytics, events and later ML labels; document how legacy integer IDs coexist with keys until
   a future additive migration.
5. [x] **Complete TAX-03 current-to-target mapping.** Provide one row for every current category
   ID 1–10 and subcategory ID 1–41 with `keep`, `rename`, `move`, `split`, `merge` or `retire`, its
   target key(s), reason, and handling implications for transactions, learned/user/system rules,
   categorization results, budgets and denormalized analytics documents. Splits must state that
   they require a later dry run or user review and cannot be inferred by a rename migration.
6. [x] **Validate artifacts and hand off.** Cross-check matrix keys against the mapping, ensure
   every proposed parent has a fallback and every old node is covered exactly once. Run
   `make -C services/categorization-service test` for the audit guard and `make notes-check`.
   Update the roadmap rows and this plan's Outcome, then propose separate TAX-04/TAX-05 design
   work; do not start schema or data migration work implicitly.

## TAX-01 product-review draft

This is the approved user-facing taxonomy, not a migration specification. It has **13 parent
categories and 67 subcategories**, including a parent-specific fallback in every branch. The
names are Danish display labels; stable keys belong to TAX-02 after this matrix is approved.

| Parent | Type | Definition and inclusions | Exclusions | Proposed subcategories |
|---|---|---|---|---|
| Mad & drikke | expense | Food, non-alcoholic groceries and prepared meals | Nightlife and events; receipt-level product splits | Dagligvarer; Restaurant & café; Takeaway; Kiosk; Mad & drikke — uspecificeret |
| Bolig | expense | Cost of occupying, supplying and maintaining the home | Loan principal; movable consumer goods; insurance unrelated to housing | Husleje; Energi & forsyning; Ejer-/boligforening; Vedligeholdelse & reparation; Bolig — uspecificeret |
| Transport | expense | Daily mobility and vehicle operation | Travel accommodation; vehicle-loan principal; cash withdrawal | Offentlig transport; Brændstof & opladning; Parkering & vejafgifter; Bilservice & reparation; Cykel & mikromobilitet; Transport — uspecificeret |
| Tjenester & forsikring | expense | Contracted services and insurance premiums where purpose is identifiable from bank data | Recurrence itself as a category; loan fees; public charges | Mobil & internet; Digitale tjenester; Medlemskaber; Forsikring; Tjenester — uspecificeret |
| Sundhed & personlig pleje | expense | Treatment, medicine and personal-care services/products | Fitness memberships; ordinary clothing | Apotek & medicin; Behandling; Frisør; Personlig pleje; Sundhed & pleje — uspecificeret |
| Shopping | expense | Durable and discretionary physical goods | Groceries; medical products; clearly identifiable hobby/sports spending | Tøj & sko; Elektronik; Møbler & boligudstyr; Byggemarked & DIY; Shopping — uspecificeret |
| Fritid & oplevelser | expense | Leisure activities, culture, nightlife, games and sport | Travel transport/accommodation; recurring digital services | Bar & natteliv; Kultur & arrangementer; Sport & fitness; Gaming & hobby; Fritid — uspecificeret |
| Rejser | expense | Purchases whose purpose is a trip rather than daily mobility | Local commuting; restaurant purchases without trip evidence | Fly & langdistance; Overnatning; Pakkerejse; Rejser — uspecificeret |
| Familie & uddannelse | expense | Dependants, gifts, pets, donations and learning | Ordinary household shopping; public fines/tax | Børn & institution; Uddannelse & materialer; Gaver & donationer; Kæledyr; Familie & uddannelse — uspecificeret |
| Offentligt & skat | expense | Taxes and mandatory payments to public authorities | Public benefits received; loan interest; utilities | Skat; Bøder; Offentlige gebyrer; Offentligt — uspecificeret |
| Finansielle omkostninger | expense | Fees and interest paid for financial services | Principal, investing and savings movements; insurance premiums | Bankgebyrer; Renteudgifter; Låne- & valutagebyrer; Finansielle omkostninger — uspecificeret |
| Indkomst | income | External inflows that increase disposable income | Own-account transfers, loan proceeds, investment sale proceeds and refunds that reverse spending | Løn; Selvstændig & freelance; Offentlig støtte; Pension & feriepenge; Kapitalindkomst; Refusion; Anden indkomst |
| Overførsler & formue | transfer | Movements that change account placement, assets or liabilities without being consumption/income | Merchant payments with known purpose; fees and interest | Egne konti & opsparing; Investering; Låneafdrag; Kreditkortbetaling; Kontanthævning; Personoverførsel; Ukendt overførsel |

### Leaf definitions and acceptance examples

The parent table owns the boundaries; these examples make every proposed leaf testable without
requiring receipt data.

- **Mad & drikke:** `Dagligvarer` = supermarkets and food shops (Netto); `Restaurant & café` =
  on-premise prepared food/drink (restaurant or café); `Takeaway` = prepared food delivered or
  collected (Wolt); `Kiosk` = convenience/kiosk purchases (7-Eleven); fallback = food purpose
  known but no safer leaf.
- **Bolig:** `Husleje` = rent; `Energi & forsyning` = electricity, water, heat and waste;
  `Ejer-/boligforening` = owner/tenant association payments; `Vedligeholdelse & reparation` =
  labour and property repair; fallback = housing purpose known but no safer leaf. Mortgage
  principal is not housing consumption; a mixed mortgage payment remains reviewable until it can
  be split into principal, interest and fees.
- **Transport:** `Offentlig transport` = bus, rail, metro and ordinary ferry; `Brændstof &
  opladning` = fuel/EV charging; `Parkering & vejafgifter` = parking, bridge and road charges;
  `Bilservice & reparation` = workshop, tyres and service; fallback = daily mobility known but no
  safer leaf. Financing principal is a transfer.
- **Tjenester & forsikring:** `Mobil & internet` = telecom connectivity; `Digitale tjenester` =
  streaming, cloud and software; `Medlemskaber` = unions, associations and non-sport memberships;
  `Forsikring` = all premiums when subtype is unavailable reliably; fallback = contracted service
  known but purpose unclear. Recurring status remains metadata, not the classification rule.
- **Sundhed & personlig pleje:** `Apotek & medicin` = pharmacies/prescription medicine;
  `Behandling` = doctor, dentist, physiotherapy and similar; `Frisør` = hair services; `Personlig
  pleje` = cosmetics/hygiene and care services; fallback = health/care purpose known but unclear.
- **Shopping:** `Tøj & sko` = clothing/footwear; `Elektronik` = devices and electronics;
  `Møbler & boligudstyr` = movable home goods; `Byggemarked & DIY` = materials/tools; fallback =
  retail purchase whose product purpose cannot be inferred. Broad merchants such as Normal and
  Power should normally land here or in review, not in a confident narrower rule.
- **Fritid & oplevelser:** `Bar & natteliv` = drinking/nightlife venues; `Kultur & arrangementer`
  = cinema, theatre, museum and tickets; `Sport & fitness` = participation, facilities and sports
  equipment; `Gaming & hobby` = games and identifiable hobbies; fallback = leisure purpose known
  but unclear.
- **Rejser:** `Fly & langdistance` = flights and explicitly trip-oriented long-distance tickets;
  `Overnatning` = hotel/hostel/holiday accommodation; `Pakkerejse` = combined travel products;
  fallback = trip context known but component unclear. Restaurants and shopping stay in their
  ordinary purpose categories unless a later trip dimension is introduced.
- **Familie & uddannelse:** `Børn & institution` = childcare and direct child costs; `Uddannelse
  & materialer` = fees, courses and study materials; `Gaver & donationer` = gifts and charitable
  donations; `Kæledyr` = veterinary care, food and supplies; fallback = family/learning purpose
  known but unclear.
- **Offentligt & skat:** `Skat` = tax payments; `Bøder` = penalties; `Offentlige gebyrer` =
  authority charges that are neither tax nor penalty; fallback = public-authority payment with
  unclear purpose.
- **Finansielle omkostninger:** `Bankgebyrer` = account/card/service fees; `Renteudgifter` =
  interest paid; `Låne- & valutagebyrer` = origination, brokerage and FX costs; fallback =
  financial-service cost with unclear subtype.
- **Indkomst:** `Løn` = employment pay; `Selvstændig & freelance` = business/freelance receipts;
  `Offentlig støtte` = benefits and study support; `Pension & feriepenge` = pension/holiday pay;
  `Kapitalindkomst` = interest and dividends actually paid in cash; `Refusion` = unlinked expense
  reimbursements/refunds; `Anden indkomst` = external income whose source is not safer to infer.
- **Overførsler & formue:** `Egne konti & opsparing` = evidenced own-account movements;
  `Investering` = asset purchase/sale and transfers to brokers; `Låneafdrag` = principal only;
  `Kreditkortbetaling` = settlement of a card balance; `Kontanthævning` = ATM cash movement;
  `Personoverførsel` = otherwise unknown person-to-person movement; `Ukendt overførsel` = transfer
  direction known but neither ownership nor purpose is established.

### Boundary decisions proposed for approval

1. **Investment:** asset purchases/sales are transfers; dividends are income; brokerage/FX fees
   are expenses.
2. **Loans and mortgages:** principal is a transfer/liability movement; interest and fees are
   expenses. A compound payment is reviewable unless the source supplies a trustworthy split.
3. **Refunds:** a refund linked to an original transaction reverses that transaction's category
   in analytics. An unlinked reimbursement uses `Indkomst → Refusion`; it must not silently look
   like salary.
4. **MobilePay/payment channel:** known merchants use spending purpose. An otherwise unknown
   person payment uses `Personoverførsel`; direction alone does not establish income/expense.
5. **Cash withdrawal:** transfer by default; later cash consumption cannot be inferred.
6. **Travel:** retain a compact travel category for transport/accommodation packages, but keep
   food/shopping in their ordinary categories. A future trip dimension can group them without
   changing spending purpose.
7. **Subscriptions:** recurrence is metadata. The purpose category wins; only telecom, digital
   services and memberships live under `Tjenester & forsikring`.
8. **Internal transfers:** auto-classify as `Egne konti & opsparing` only with account-ownership
   evidence. Description matching alone falls back to `Ukendt overførsel` and review.

## TAX-02 stable keys and lifecycle

The accepted identity/lifecycle policy is canonical in the
[decision](../decisions/2026-08-01-taxonomy-semantics-and-identity.md). The target vocabulary below
is the complete key registry for this taxonomy version. Keys are flat so a later parent move does
not change child identity.

| Parent key | Display name | Child keys in display order |
|---|---|---|
| `food_drink` | Mad & drikke | `groceries`; `restaurant_cafe`; `takeaway`; `kiosk`; `food_drink_unspecified` |
| `housing` | Bolig | `rent`; `home_utilities`; `housing_association`; `home_maintenance`; `housing_unspecified` |
| `transport` | Transport | `public_transport`; `fuel_charging`; `parking_tolls`; `vehicle_service`; `cycling_micromobility`; `transport_unspecified` |
| `services_insurance` | Tjenester & forsikring | `mobile_internet`; `digital_services`; `memberships`; `insurance`; `services_unspecified` |
| `health_personal_care` | Sundhed & personlig pleje | `pharmacy_medicine`; `treatment`; `hairdresser`; `personal_care`; `health_care_unspecified` |
| `shopping` | Shopping | `clothing_footwear`; `electronics`; `furniture_homeware`; `hardware_diy`; `shopping_unspecified` |
| `leisure_experiences` | Fritid & oplevelser | `bar_nightlife`; `culture_events`; `sport_fitness`; `gaming_hobby`; `leisure_unspecified` |
| `travel` | Rejser | `flight_long_distance`; `accommodation`; `package_travel`; `travel_unspecified` |
| `family_education` | Familie & uddannelse | `children_childcare`; `education_materials`; `gifts_donations`; `pets`; `family_education_unspecified` |
| `public_tax` | Offentligt & skat | `tax`; `fines`; `public_fees`; `public_unspecified` |
| `financial_costs` | Finansielle omkostninger | `bank_fees`; `interest_expense`; `loan_fx_fees`; `financial_costs_unspecified` |
| `income` | Indkomst | `salary`; `self_employment`; `public_benefits`; `pension_holiday_pay`; `capital_income`; `refund`; `other_income` |
| `transfers_wealth` | Overførsler & formue | `own_accounts_savings`; `investment`; `loan_principal`; `credit_card_settlement`; `cash_withdrawal`; `person_transfer`; `unknown_transfer` |

`other_income` and `unknown_transfer` are the explicit fallbacks for their parents; every other
fallback ends in `_unspecified`. A future schema constraint should enforce one active fallback per
parent. UUIDv7 values are generated once in TAX-06 and pinned in the additive migration/fixture;
this plan intentionally does not invent UUIDs before that executable source of truth exists.

## TAX-03 current-to-target mapping

### Current categories (IDs 1–10)

| ID | Current node | Disposition | Target key(s) | Existing-data implication |
|---:|---|---|---|---|
| 1 | Mad & drikke | keep | `food_drink` | Preserve category assignment; child merges handle café. |
| 2 | Bolig | keep | `housing` | Preserve clear housing assignments; insurance/telecom children move out. |
| 3 | Transport | keep | `transport` | Preserve category; child names become more explicit. |
| 4 | Underholdning & fritid | rename | `leisure_experiences` | Safe parent rename except subscription rules move to services. |
| 5 | Personlig | split | `health_personal_care`, `shopping` | Child ID decides deterministic target; parent-only rows require review. |
| 6 | Hjem | split | `housing`, `shopping` | Child ID decides target; parent-only rows require review. |
| 7 | Finansielt | split | `financial_costs`, `transfers_wealth` | Investment must leave expense metrics; parent-only rows require review. |
| 8 | Diverse | split | typed target fallbacks | Never bulk-map blindly; use known child/rule evidence, otherwise amount direction plus review. |
| 9 | Indkomst | keep | `income` | Preserve genuine income; transfers/refunds follow child mapping and evidence. |
| 10 | Overfoersler | rename | `transfers_wealth` | Preserve transfer type; MobilePay no longer determines purpose. |

### Current subcategories (IDs 1–41)

| ID | Current node | Disposition | Target key(s) | Rule/transaction handling |
|---:|---|---|---|---|
| 1 | Dagligvarer | keep | `groceries` | Direct remap; retain safe grocery rules. |
| 2 | Restaurant | merge | `restaurant_cafe` | Direct remap. |
| 3 | Takeaway | keep | `takeaway` | Direct remap. |
| 4 | Kaffebar | merge | `restaurant_cafe` | Direct remap; café keyword needs ambiguity audit. |
| 5 | Kiosk | keep | `kiosk` | Direct remap. |
| 6 | Husleje | keep | `rent` | Direct remap. |
| 7 | El/vand/varme | rename | `home_utilities` | Direct remap. |
| 8 | Forsikring | move | `insurance` | Preserve labels/budgets under new parent. |
| 9 | Mobil/internet | move | `mobile_internet` | Preserve labels/budgets under new parent. |
| 10 | Vedligeholdelse | rename | `home_maintenance` | Direct remap when housing purpose is known. |
| 11 | Offentlig transport | keep | `public_transport` | Direct remap. |
| 12 | Braendstof | rename | `fuel_charging` | Direct remap; add charging rules later. |
| 13 | Bil/vedligeholdelse | rename | `vehicle_service` | Direct remap. |
| 14 | Parkering | rename | `parking_tolls` | Direct remap; add toll rules later. |
| 15 | Cykel | rename | `cycling_micromobility` | Direct remap. |
| 16 | Abonnementer | split | `digital_services`, `memberships`, purpose category | Existing rows/rules require merchant-level dry run; recurrence alone cannot choose. |
| 17 | Barer/natteliv | rename | `bar_nightlife` | Direct remap; broad `bar` rule requires audit. |
| 18 | Oplevelser | split | `culture_events`, `gaming_hobby`, `leisure_unspecified` | Rules determine safe targets; remaining rows need review. |
| 19 | Fitness/sport | rename | `sport_fitness` | Direct remap. |
| 20 | Sportstoj/udstyr | split | `sport_fitness`, `clothing_footwear`, `shopping_unspecified` | Merchant/product ambiguity requires dry run or review. |
| 21 | Pleje/hygiejne | rename | `personal_care` | Direct remap only for specific rules; broad retailers require review. |
| 22 | Haarpleje | rename | `hairdresser` | Direct remap. |
| 23 | Medicin | rename | `pharmacy_medicine` | Direct remap. |
| 24 | Toj | move | `clothing_footwear` | Direct remap under Shopping. |
| 25 | Mobler/DIY | split | `furniture_homeware`, `hardware_diy` | Merchant rules split; ambiguous existing rows need review. |
| 26 | Elektronik | move | `electronics` | Direct remap; broad `power` rule requires audit. |
| 27 | Gebyrer | split | `bank_fees`, `loan_fx_fees`, `financial_costs_unspecified` | Description/rule evidence required; no blind narrow mapping. |
| 28 | Renteudgifter | keep | `interest_expense` | Direct remap. |
| 29 | Investering | move/type correction | `investment` | Remove from expense analytics; preserve as transfer with explicit audit. |
| 30 | Kontant/ATM | move/type correction | `cash_withdrawal` | Remove from expense analytics; preserve as transfer. |
| 31 | Vaskeri | move/merge | `services_unspecified` | Preserve as service fallback until a useful dedicated leaf is justified. |
| 32 | Anden | split | parent-specific fallback or `unknown_transfer`/`other_income` | Direction supplies only type; all rows remain reviewable. |
| 33 | Lon | rename | `salary` | Direct remap. |
| 34 | Offentlig stotte | rename | `public_benefits` | Direct remap; split pension/holiday-pay rules where evidenced. |
| 35 | Overforsel fra andre | split/type review | `person_transfer`, `other_income`, `refund` | Evidence required; inbound direction alone is not income. |
| 36 | Renteindtaegter | rename | `capital_income` | Direct remap. |
| 37 | Opsparing (ind) | move/type correction | `own_accounts_savings` | Remove from income analytics; require ownership evidence. |
| 38 | MobilePay ind | split | purpose category or `person_transfer` | Re-evaluate merchant/person evidence; channel is not purpose. |
| 39 | MobilePay ud | split | purpose category or `person_transfer` | Re-evaluate merchant/person evidence; channel is not purpose. |
| 40 | Kontooverforsel | split | `own_accounts_savings`, `person_transfer`, `unknown_transfer` | Ownership/counterparty evidence required. |
| 41 | Opsparing (ud) | rename | `own_accounts_savings` | Direct only with ownership evidence; otherwise `unknown_transfer`. |

### Cross-reference handling

- **Transactions and categorization results:** keep their original assignment and provenance until
  TAX-07 runs an approved dry run. Deterministic keep/rename/move/merge rows can be proposed for
  bulk remap; every split stays reviewable.
- **System, user and learned rules:** retarget only one-to-one rows automatically. Split rows are
  disabled or held for rule/merchant audit; user intent is never guessed from a global mapping.
- **Budgets:** one-to-one rows retain the amount under the target UUID. Split parent budgets do
  not get apportioned automatically; users receive a review/default proposal.
- **Analytics:** versioned taxonomy events repair names/hierarchy, while transaction documents
  change grouping only after the source assignment changes. Type corrections for investment,
  cash and savings need explicit before/after consumption totals in TAX-07.

## Risks & rollback

- **Semantics optimize for implementation rather than user comprehension.** Detect through the
  boundary examples and product checkpoint; revise the documents before any schema exists.
- **A rename is mistaken for identity preservation when meaning changed.** Detect by requiring
  definition/inclusion/exclusion diffs and explicit split/merge dispositions. Rollback is a
  document revision because this phase performs no data writes.
- **Pinned integer IDs leak into the target as semantic identity.** Detect by requiring a stable
  key on every matrix/mapping row and checking downstream groupings separately. No database
  rollback is needed in this phase.
- **Existing rules or budgets lose a target in the proposed mapping.** Detect with the audit
  helper and complete impact columns. Block TAX-04 onward until every reference class has a
  stated disposition.

## Outcome (fill in when done)

Completed 2026-08-01. The approved target is a purpose-first taxonomy with 13 categories and 67
subcategories, explicit per-parent fallbacks and eight resolved boundary rules. The identity
decision separates UUIDv7 protocol identity, immutable flat semantic keys, mutable display names
and legacy integer surrogates. The mapping covers all 10 current categories and 41 current
subcategories exactly once; split cases are explicitly blocked from blind bulk remapping and
carry handling for transactions/results, rules, budgets and analytics.

Added `tests/unit/test_taxonomy_baseline.py` to pin the verified current 10/41 IDs/types/order,
130 rule targets, name uniqueness and the single current fallback. Verification: 168 fast tests
passed; Ruff, formatting and mypy passed; structured document check found 10/41 mapping rows and
80 unique target keys (13 + 67); `make notes-check` and `git diff --check` passed. No schema,
migration, seed or user-data write was made. Next work is a separately approved TAX-04/TAX-05
plan for seed-concept design and rule quality; TAX-06 remains the first production migration.
