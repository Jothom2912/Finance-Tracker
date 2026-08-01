---
title: Purpose-first taxonomy with UUIDv7 identity and stable semantic keys
date: 2026-08-01
status: accepted
backlog: [TAX-01, TAX-02, TAX-03]
supersedes: null
promoted-to-adr: null
---

# Purpose-first taxonomy with UUIDv7 identity and stable semantic keys

## Decision

The default taxonomy is the approved 13-parent, 67-child purpose-first matrix in the
[TAX-01–03 plan](../plans/2026-08-01-tax01-tax03-taxonomy-foundation.md). Payment channel and
recurrence are features, while asset/liability movements are transfers rather than consumption
or income.

Each future taxonomy node has three distinct identifiers: a UUIDv7 `public_id` as canonical
cross-service identity, an immutable globally unique ASCII `key` for rules/configuration/training
labels, and the existing integer `id` as a legacy database surrogate during migration. Display
names are mutable and never identity.

## Context

The current 10/41 taxonomy uses pinned integers across services and mutable names in seed rules.
It mixes spending purpose with payment channel (`MobilePay`), financial movement
(`Investering`) and recurrence (`Abonnementer`). That inflates consumption metrics and makes
renames unsafe for durable ML labels. The choice preserves ADR-003's ownership and event-based
read copies; it changes semantics and future identity, not service ownership.

The product review on 2026-08-01 explicitly approved the matrix and eight boundary rules for
investments, loans, refunds, MobilePay, cash, travel, subscriptions and internal transfers.

## Alternatives considered

- **Keep pinned integers as canonical identity** — rejected because new cross-service identifiers
  must use UUIDv7, integers are environment/migration coupled, and they do not provide readable
  stable labels for rule definitions or ML fixtures.
- **Use a hierarchical slug such as `expense.food.groceries` as the only identity** — rejected
  because moving a node or correcting its type would either change identity or leave a misleading
  path. A flat immutable key survives hierarchy changes; UUIDv7 remains the protocol identity.
- **Use display names as labels and propagate renames** — rejected because analytics, budgets,
  rules and training labels would acquire semantic drift from a presentation edit.
- **Categorize by payment channel or recurrence** — rejected because MobilePay/card/transfer and
  subscription status do not state spending purpose. They remain orthogonal features.
- **Count investments, principal and cash withdrawals as expenses** — rejected because this
  overstates consumption; they move assets or liabilities. Only interest and fees are expenses.
- **Remove travel as a category in favour of a future trip dimension** — rejected for now because
  flight/accommodation/package purchases are useful from bank data today. Ordinary food and
  shopping still keep their purpose category, allowing a later trip dimension without remapping.

## Consequences

- Renames only alter display fields; a meaning change creates a new UUID/key and deprecates the
  old node with an explicit replacement or split mapping.
- Keys are lowercase ASCII `snake_case`, globally unique within node kind, and do not encode
  parent or type. They are never recycled after deprecation.
- Each parent has exactly one fallback child. Fallback is explicit metadata (`is_fallback`), not
  inferred from a Danish name.
- Taxonomy changes carry a monotonically increasing integer version. Add/remove/move/type,
  fallback and definition changes increment it; spelling-only display changes also increment the
  published snapshot version so consumers can repair deterministically.
- Nodes are soft-deprecated (`deprecated_in_version`, optional `replaced_by_public_id`); split
  replacements use a separate one-to-many migration mapping and require review/dry-run.
- A later additive migration must introduce UUIDv7 IDs, keys, lifecycle fields and versioned
  full-state events before production labels or data are remapped. Existing integer foreign keys
  remain valid throughout the compatibility window.
- This does not require a new ADR: ADR-003's owner and communication model are unchanged. Event
  contract evolution and rollout mechanics belong to TAX-04–06.
