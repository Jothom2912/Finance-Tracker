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
  **Paths amended 2026-07-29 — the writes moved to `/api/v1/internal/…`;
  see [Amendments](#amendments). Ownership is unchanged.**
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

## Amendments

### 2026-07-29 — taxonomy writes moved behind `X-Internal-API-Key` (P2-28)

**What changed:** the six write routes moved off the public prefixes.
Reads are untouched.

| Then (this ADR, as decided) | Now |
|---|---|
| `POST /api/v1/categories/` | `POST /api/v1/internal/categories/` |
| `PUT /api/v1/categories/{id}` | `PUT /api/v1/internal/categories/{id}` |
| `DELETE /api/v1/categories/{id}` | `DELETE /api/v1/internal/categories/{id}` |
| `POST /api/v1/categories/{id}/subcategories` | `POST /api/v1/internal/categories/{id}/subcategories` |
| `PUT /api/v1/subcategories/{id}` | `PUT /api/v1/internal/subcategories/{id}` |
| `DELETE /api/v1/subcategories/{id}` | `DELETE /api/v1/internal/subcategories/{id}` |
| `GET /api/v1/categories/`, `/{id}`, `/{id}/subcategories`, `GET /api/v1/subcategories/` | **unchanged**, JWT |

The write router carries `require_internal_api_key` at router level;
ADR-0005's deny-backstop (`location /api/ { return 404; }`) means the
perimeter answers 404 for the whole `/api/v1/internal/` prefix, so no
nginx change was needed.

**What did *not* change: ownership.** This ADR settled *who writes the
taxonomy*; P2-28 settled *who may ask it to*. categorization-service is
still the sole owner and writer, still emits the same full-state
`category.*` / `subcategory.*` events from the same outbox, and
transaction-service's read copies are unaffected. The delete guards in
"Delete guards" above are also untouched — no guard was added or removed.

**One thing in Context above is now history:** the "taxonomy management
UI" listed there as the trigger for this ADR
(`components/CategoryManagement/`) was deleted by P2-28 — it could not
stay and call routes that answer 405. It was true when this ADR was
written; don't go looking for it. Its replacement, if the need returns,
is per-user custom categories (**F2-15**) rather than a UI onto shared
global state.

**Why it was needed:** this ADR's write routes took
`_user_id: int = Depends(get_current_user_id)` — identity resolved and
discarded — so any authenticated user could write shared data. Measured
before the fix: a user registered one minute earlier, owning zero
transactions, renamed a category and analytics-service's
`propagate_category_rename` rewrote the denormalized `category_name` on
**150 documents across 23 other users** in Elasticsearch. No delete
guard could have caught it, because a rename orphans nothing — which is
why the fix is authorization in the adapter layer rather than another
entry in the delete-guard list.

Details: [decision](../dev-notes/decisions/2026-07-29-taxonomy-authorization.md) ·
[plan + Outcome](../dev-notes/plans/2026-07-29-p228-taxonomy-internal-only.md#outcome).

## Exit criteria of ADR-002 (for the record)

Executed via criterion 1: the category/subcategory feature work
naturally rewired every touchpoint this ADR lists.

## Supersedes

ADR-002 (status updated to Superseded).
