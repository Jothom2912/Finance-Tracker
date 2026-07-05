# ADR-003: Taxonomy ownership consolidated into categorization-service

## Status

Accepted — supersedes ADR-002 ("decision A" executed)

## Context

ADR-002 deferred the transfer of category ownership as a separate epic
with explicit exit criteria. Exit criterion 1 ("next major feature
touches categories") was met by the category/subcategory end-to-end
work (subcategory exposure, dashboard drill-down, taxonomy management
UI). Before this ADR:

- The `categories` table existed in **both** transaction-service
  (authoritative writer, CRUD API, `category.*` events) and
  categorization-service (event-synced copy — which however owned the
  only `subcategories`, `merchants`, and `categorization_rules` tables).
- Reads had no single source: frontend/gateway read from
  transaction-service; budget-service read from categorization-service.
- The seed list was hand-duplicated in four files; no API could create
  subcategories at all; subcategories were dropped at every read
  boundary (gateway GraphQL, frontend).

## Decision

**categorization-service is the sole owner of the full taxonomy**
(parent categories + subcategories):

- Full category CRUD and new subcategory CRUD live in
  categorization-service (`/api/v1/categories`, nested subcategory
  create/list, flat `/api/v1/subcategories` for list-all/update/delete).
- It emits full-state events via its transactional outbox:
  - `category.created|updated|deleted` **v2** — adds `display_order`,
    drops the unused `previous_name`/`previous_type` delta fields.
  - `subcategory.created|updated|deleted` **v1** — full state
    (`subcategory_id`, `name`, `category_id`, `is_default`). Note:
    a topic binding on `category.*` does NOT match `subcategory.*`;
    consumers bind both.
- **transaction-service holds event-synced read copies** (`categories`
  without `display_order` — ordering is presentation and served by the
  owner; a new `subcategories` table for name denormalization and
  subcategory-belongs-to-category validation). The
  `transaction_service.taxonomy_sync` consumer maintains them with
  self-healing upserts and inbox idempotency. Fresh databases bootstrap
  the copies via migration seeds because outbox events published before
  the consumer queue is declared are dropped by the topic exchange;
  categorization-service migration 006 additionally re-announces the
  seed taxonomy (and heals `display_order=0` drift left by the old
  sync consumer) for existing databases.
- **Gateway, frontend, and budget-service all read taxonomy from
  categorization-service.** transaction-service's category endpoints
  (including GET) are removed; its migration 006 is a tombstoned no-op.
  The gateway's legacy monolith key renames (`idCategory`,
  `Category_idCategory`, `idTransaction`, `Account_idAccount`) are
  gone — normalized `id`/`category_id`/`subcategory_id` throughout.
- `transaction.categorized` is bumped to **v2** with `category_name`
  (parent name), removing the stale-name window where the consumer
  could not resolve the parent locally. Empty string means "v1
  payload" and triggers the local-lookup fallback.
- Dashboard aggregation is **id-keyed** (`category_id`, None =
  "Ukategoriseret") with a nested subcategory breakdown per bucket,
  including a `subcategory_id: null` remainder bucket
  ("(Ingen underkategori)").

## Delete guards (and one deliberately dropped)

Guards enforced in categorization-service, all local and deterministic:

- Deleting a **category** with subcategories → 409 (children must be
  deleted/moved first).
- Deleting a **subcategory** referenced by `merchants` or
  `categorization_rules`, or literally named "Anden" (the rule
  engine's fallback) → 409.

**Deliberately dropped:** transaction-service's old
`CategoryInUseException` ("category referenced by transactions") has no
equivalent. A cross-service HTTP count check would invert the
dependency direction (the taxonomy owner synchronously depending on a
downstream consumer) and is TOCTOU-racy anyway. Transactions carry
denormalized `category_name`/`subcategory_name`, so historical display
survives deletion; the dashboard buckets orphaned ids under
"Ukategoriseret". The children-first rule makes accidental deletion of
seeded categories effectively impossible.

## Identifiers

Category ids 1–10 and subcategory ids 1–41 remain pinned ints
(originating from the monolith MySQL auto-increment order). Re-keying
to UUIDs was rejected: every service and existing rows reference the
int ids, and the migration churn would buy nothing — the ids are
internal to the system.

## Consequences

**Positive:**
- Exactly one writer and one read source for the whole taxonomy.
- Subcategories are first-class end-to-end: CRUD API, events, read
  copies, gateway exposure, cascading picker, dashboard drill-down.
- Id-keyed aggregation ends name-collision/rename bugs and the silent
  drop of "Ukategoriseret" in filters.

**Negative / accepted costs:**
- transaction-service depends on event delivery for name resolution;
  a lagging sync consumer means fallback to caller-provided or event
  names (logged, self-healing on next event).
- Brief breaking window during cutover: `/api/v1/categories` on :8002
  404s until gateway/frontend re-point — loud failure preferred over
  silent divergence (dev project, single deploy train).
- ai-service's dashboard parsing was coupled to the REST shape and had
  to change with it (updated in the same train).

## Exit criteria of ADR-002 (for the record)

Executed via criterion 1: the category/subcategory feature work
naturally rewired every touchpoint this ADR lists.

## Supersedes

ADR-002 (status updated to Superseded).
