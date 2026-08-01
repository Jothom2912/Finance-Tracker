# Taxonomy optimization roadmap

Companion to [ML-CATEGORIZATION.md](ML-CATEGORIZATION.md) and
[AI-IMPROVEMENTS.md](AI-IMPROVEMENTS.md). IDs `TAX-xx` are stable and should be used by
the later implementation plan.

## Goal

Establish a stable, useful Danish personal-finance taxonomy before sandbox personas,
manual labels and ML training data accumulate. The taxonomy should support budgets,
analytics and AI answers while remaining learnable from ordinary bank transaction data.

This is a **roadmap, not an approved implementation plan**. Before changing domain data,
migrations or event flows, create a plan with `dev-notes-plan` and wait for approval.

## Verified current state (2026-08-01)

- `categorization-service` is the sole taxonomy writer under ADR-003; transaction-service
  and analytics/Elasticsearch maintain event-synced read copies.
- `services/categorization-service/app/domain/taxonomy.py` defines 10 categories, 41
  subcategories and 130 keyword-to-subcategory seed mappings.
- Categories have only a mutable display `name`, integer id, type and display order. There
  is no stable slug, description, synonym set or lifecycle state.
- Category type already distinguishes `expense`, `income` and `transfer`, but some current
  placements violate that distinction: investment is an expense and savings is split
  between income and transfer.
- `SEED_MERCHANT_MAPPINGS` currently combines merchant identification, aliases and the
  categorization rule in one dictionary. Some entries are broad text fragments or
  personal merchants rather than safe global defaults.
- Seed changes must be additive migrations. Migration 006 is the reference for emitting
  full-state taxonomy events so existing read copies are healed.
- Global taxonomy writes are internal-only. Per-user custom categories remain separate
  future scope under F2-15.

## Product rules for the redesign

1. A category must produce a useful distinction in a budget, insight or AI answer.
2. Categories and subcategories should be mutually understandable to a user; ambiguous
   cases must have an explicit fallback.
3. The default taxonomy must be learnable from bank data. Details that require receipts
   should not become default subcategories.
4. Precision beats coverage. Unknown data should reach a reviewable fallback instead of a
   confident but weak global rule.
5. Transfers, savings, investments, loan principal and credit-card settlement must not
   inflate consumption or income metrics.
6. Payment channel is not spending purpose. MobilePay, card and bank transfer should be
   stored as features; only use person-to-person transfer as a fallback when purpose is
   unknown.
7. Display names may change without changing semantic identity. Training labels, budgets
   and analytics group by stable identifiers, never names.
8. Synthetic/sandbox labels, rule-derived labels and manually confirmed labels remain
   distinguishable (`synthetic`, `silver`, `gold`).

## Candidate default taxonomy

The exact names and boundaries are proposals to validate during TAX-01. Aim for roughly
12–15 categories and 50–70 subcategories: enough analytical detail without creating sparse
classes.

| Category | Type | Candidate subcategories |
|---|---|---|
| Mad & drikke | expense | Dagligvarer; Restaurant; Takeaway; Cafe; Kiosk |
| Bolig | expense | Husleje; Realkredit/boliglaan; El; Vand; Varme; Vedligeholdelse; Ejer-/boligforening |
| Transport | expense | Offentlig transport; Braendstof; Parkering; Bilservice; Leasing/billaan; Taxi; Cykel; Bro/faerge |
| Faste tjenester | expense | Mobil; Internet; Streaming; Software/digitale tjenester; Medlemskaber; Andre abonnementer |
| Forsikring | expense | Indbo; Bil; Ulykke; Rejse; Sundhed; Anden forsikring |
| Sundhed & personlig pleje | expense | Apotek/medicin; Behandling; Frisoer; Kosmetik/pleje; Briller/kontaktlinser |
| Toej & shopping | expense | Toej; Sko; Elektronik; Moebler/boligudstyr; Byggemarked/DIY; Anden shopping |
| Fritid & oplevelser | expense | Bar/natteliv; Kultur; Gaming; Hobby; Fitness/sport; Sportsudstyr; Arrangementer |
| Rejser | expense | Fly; Hotel/overnatning; Pakkerejse; Lokal transport; Rejseaktiviteter |
| Familie & relationer | expense | Boern/institution; Lommepenge; Gaver; Donationer; Kaeledyr; Underholdsbidrag |
| Uddannelse | expense | Studieafgift; Boeger/materialer; Kurser; Studietransport |
| Offentligt & skat | expense | Skat; Kommunale betalinger; Boeder; Offentlige gebyrer |
| Finansielle omkostninger | expense | Bankgebyrer; Renteudgifter; Laaneomkostninger; Valutagebyrer |
| Indkomst | income | Loen; Selvstaendig/freelance; Offentlig stoette; Pension; Feriepenge; Renteindtaegt; Udbytte; Refusion; Anden indkomst |
| Overfoersler & formue | transfer | Egne konti; Opsparing; Investering; Laaneafdrag; Kreditkortbetaling; MobilePay til person; MobilePay fra person; Kontanthaevning; Ukendt overfoersel |

Each parent should have a parent-specific fallback such as `Mad & drikke — uspecificeret`.
For transactions where even the parent is unknown, use typed review buckets (`Ukendt koeb`,
`Ukendt indbetaling`, `Ukendt overfoersel`) rather than hiding model quality under `Diverse`.

## Known boundary cases to decide explicitly

- **Investment:** asset purchase/sale is transfer; brokerage and currency fees are expense;
  dividend and realized cash income are income.
- **Loans:** principal is transfer/liability movement; interest and fees are expense.
- **Refunds:** decide whether product analytics reverses the original expense category or
  presents a separate income-like refund. Preserve the link/source either way.
- **MobilePay:** merchant payments use their actual purpose; person-to-person direction is a
  fallback, not a universal category.
- **Cash withdrawal:** transfer by default; later cash spending cannot be inferred without
  user input.
- **Travel:** decide whether travel merchants remain in their ordinary categories with a
  trip dimension, or use a dedicated category. A trip dimension is analytically stronger
  but is outside the first taxonomy change.
- **Subscriptions:** recurring status is a feature. The category expresses purpose; decide
  whether `Faste tjenester` is worth the convenient overview or duplicates purpose-based
  categories.
- **Internal transfers:** require ownership/account evidence where possible; description
  matching alone is not strong enough for confident auto-application.

## Seed model target

Keep three concepts separate:

1. **Taxonomy definitions** — stable slug, display name, type, parent, description,
   synonyms, fallback marker and lifecycle/version metadata.
2. **Merchant aliases** — canonical merchant plus provider-specific text variants.
3. **Categorization rules** — merchant/pattern to target subcategory, with constraints and
   provenance.

Candidate rule constraints are transaction direction, match field (merchant/counterparty
versus free text), amount range, provider/country and confidence. Every global seed should
carry provenance and a seed version. Generic fragments such as `bar`, `cafe`, `power`,
`normal`, `su` and `rente` need an ambiguity review; personal names and local one-off
merchants should be removed from global defaults or moved into persona fixtures.

## Roadmap

| ID | Work item | Output | Depends on | Status |
|---|---|---|---|---|
| TAX-01 | Taxonomy audit and definitions | Approved category matrix with definitions, inclusions, exclusions and boundary-case decisions | — | done 2026-08-01 — [plan](../plans/2026-08-01-tax01-tax03-taxonomy-foundation.md) + [decision](../decisions/2026-08-01-taxonomy-semantics-and-identity.md) |
| TAX-02 | Stable identity and lifecycle | Slug/key strategy, rename semantics, fallback representation, deprecation/merge policy and taxonomy version | TAX-01 | done 2026-08-01 — [decision](../decisions/2026-08-01-taxonomy-semantics-and-identity.md) |
| TAX-03 | Current-to-target mapping | Mapping for all 10/41 current nodes: keep, rename, move, split, merge or retire; impact on existing transactions/rules/budgets | TAX-01, TAX-02 | done 2026-08-01 — [mapping + Outcome](../plans/2026-08-01-tax01-tax03-taxonomy-foundation.md#tax-03-current-to-target-mapping) |
| TAX-04 | Separate seed concepts | Schema/domain design for taxonomy definitions, merchant aliases and constrained categorization rules | TAX-01, TAX-02 | open |
| TAX-05 | Seed quality audit | Review all 130 mappings; remove personal/ambiguous entries, add safe Danish merchants and direction constraints, document provenance | TAX-04 | open |
| TAX-06 | Additive migration and event repair | New migration(s), deterministic full-state events, read-copy updates and rollback/repair procedure; never edit old migrations | TAX-02–05 | open |
| TAX-07 | Existing-data reclassification strategy | Dry-run/replay report, preservation of manual decisions, rule/budget remap, explicit approval before any bulk write | TAX-03, TAX-06 | open |
| TAX-08 | Sandbox persona fixtures | Bank/provider-separated synthetic personas, expected labels, dataset source/version and reset/reimport path | TAX-05, TAX-06 | open |
| TAX-09 | Quality gate | Per-bank/category coverage, ambiguity cases and deterministic regression fixtures before labels are treated as training data | TAX-07, TAX-08; ML-01 | open |

## Recommended sequencing with ML and AI work

```text
TAX-01 definitions
  -> TAX-02 stable identity
  -> TAX-03 migration mapping + TAX-04 seed model
  -> TAX-05 seed audit
  -> TAX-06 additive migration/event repair
  -> TAX-07 dry-run reclassification
  -> TAX-08 sandbox personas
  -> TAX-09 quality gate
  -> ML-01/03/06 decision log, normalization and label store
  -> ML-04/05 baseline classifier in shadow mode
  -> AI-21 taxonomy-aware chat filters
```

Some measurement plumbing may be designed in parallel, but production labels should not
be frozen against the old taxonomy when TAX-01–03 are still unsettled.

## Non-goals for the first implementation plan

- Per-user custom taxonomy (F2-15).
- Automatic LLM categorization.
- Cross-user merchant priors.
- Receipt-level classification.
- Automatic destructive recategorization of existing user transactions.
- A generic trip/project dimension unless the travel boundary decision promotes it into a
  separate approved plan.

## Planning hand-off

The next artifact should be an implementation plan covering **TAX-01 through TAX-03 only**.
Those items settle semantics, identity and migration mapping without prematurely changing
production data. The plan must include current-code verification, affected consumers,
acceptance examples and a review checkpoint before TAX-04 onward is implemented.

Plan created: [TAX-01–03 taxonomy foundation](../plans/2026-08-01-tax01-tax03-taxonomy-foundation.md)
(awaiting approval).
