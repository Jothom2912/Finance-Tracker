---
title: TAX-06 migration collides with category IDs already allocated in a populated database
date: 2026-08-01
severity: HIGH
area: categorization-service, migrations, taxonomy
status: resolved
backlog: [P2-44]
resolved-by: ../plans/2026-08-01-p244-tax06-surrogate-id-repair.md
---

# TAX-06 migration collides with category IDs already allocated in a populated database

**Where**: `services/categorization-service/migrations/versions/008_activate_taxonomy_v1.py:60`.

**Defect**: Migration 008 inserts the 13 target parents at fixed surrogate IDs beginning with 11.
On the copied 2026-08-01 development snapshot, category ID 11 is already allocated, so the
real 007→008 upgrade fails with `categories_pkey` before TAX-06 can activate. The migration's
transaction rolled back cleanly; the active database was never targeted.

**Why it matters**: TAX-06's populated-upgrade verification did not include a database where the
runtime taxonomy API had allocated IDs after the original 10 parents. A production-shaped upgrade
can therefore remain permanently at revision 007, and TAX-07 cannot assume that the 13/67 registry
is present in every real environment even though clean/test databases pass.

**Suggested fix**: Add a new, separately approved forward migration/repair plan. Do not edit the
published migration in place. The repair must preserve existing category/subcategory references,
allocate collision-free surrogates while retaining pinned UUID/key identity, verify sequences and
events on this exact snapshot shape, and only then resume the normal 007→target rollout. TAX-07's
read-only scanner intentionally reads only legacy columns so analysis can continue without
pretending the failed TAX-06 activation succeeded.

**Plan**: [P2-44 collision-safe surrogate-ID repair](../plans/2026-08-01-p244-tax06-surrogate-id-repair.md)
is awaiting approval. It records the Alembic constraint that an unchanged 008 cannot be repaired
by a later revision alone and therefore approval must explicitly cover a fail-closed pre-008
bootstrap plus forward revision 009.
