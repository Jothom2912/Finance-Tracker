---
title: Merchant evidence, rule confidence and direction semantics
date: 2026-08-01
status: accepted
backlog: [TAX-04, TAX-05]
supersedes: null
promoted-to-adr: null
---

# Merchant evidence, rule confidence and direction semantics

## Decision

Merchant aliases identify a canonical merchant but never own a taxonomy target. A global rule
references either one canonical merchant or one normalized explicit pattern, carries its own
target and constraints, and requires provenance. Only structured merchant/counterparty evidence
may be high confidence; description-text matching is capped at medium confidence.

Direction is derived at the categorization boundary as amount `> 0` = incoming and amount `< 0`
= outgoing. A zero amount matches only a direction-agnostic rule. Optional amount bounds are
inclusive.

## Context

The legacy seed maps each text fragment directly to both a merchant display label and a mutable
subcategory name. The same fragment is applied to the complete description, and four special
keywords are reinterpreted by amount sign inside the adapter. This prevents independent alias
repair, hides weak evidence behind high-confidence results and cannot express provider-specific
or directional safety. TAX-04–05 needs a migration-ready contract before auditing the 130 global
mappings; see the [implementation plan](../plans/2026-08-01-tax04-tax05-seed-model-and-audit.md).

## Alternatives considered

- Keep a category target on the canonical merchant — rejected because one merchant or payment
  intermediary may represent several purposes, and alias maintenance would silently change
  categorization policy.
- Allow high-confidence free-text `contains` rules — rejected because short fragments collide
  with unrelated descriptions and the source field supplies less identity evidence.
- Preserve per-key sign overrides in the adapter — rejected because direction is rule evidence
  and must be visible, auditable and portable to persistence rather than hidden in code.
- Treat zero as outgoing by using the existing `amount > 0` branch — rejected because zero
  establishes no money-flow direction and must not inherit a confident category accidentally.

## Consequences

Aliases can be repaired without changing category policy, and rules can be audited by evidence,
direction, confidence and provenance. TAX-06 must persist these separate concepts and remove the
adapter's special sign table only when constrained rules are active. Provider adapters must
preserve the stated amount-sign convention or translate explicitly at their boundary. Some broad
legacy rules will lose automatic coverage; this is intentional because precision takes priority
over confident guesses.
