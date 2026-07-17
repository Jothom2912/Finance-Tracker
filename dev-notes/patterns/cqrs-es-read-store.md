---
title: "Pattern: CQRS with Elasticsearch read-store"
updated: 2026-07-17
source: ADR-0004; gateway doc 2026-07-13; AI-20 cutover 2026-07-14
---

# CQRS with Elasticsearch read-store

**Writes**: REST on the owning domain service (Postgres, database-per-service).
**Reads**: pre-aggregated from a central denormalized Elasticsearch store, served through
the gateway BFF (GraphQL via Strawberry). Formalized in
[docs/adr/0004-analytics-elasticsearch-read-store.md](../../docs/adr/0004-analytics-elasticsearch-read-store.md).

## Write → read path

1. Domain service commits + outboxes (e.g. `transaction.created`).
2. **analytics-service is the sole ES writer** (store-per-service ownership): its
   `projection_consumer.py` upserts full-state documents into ES
   ([idempotent-consumers](idempotent-consumers.md) §self-healing).
3. A **second consumer** (`embedding_consumer.py`, own queue `analytics.embeddings` +
   DLQ) partial-updates `description_vector` (bge-m3 via Ollama) — deliberately isolated
   so Ollama downtime can't stall core projections
   ([decisions/2026-07-13-embed-worker-placement](../decisions/2026-07-13-embed-worker-placement.md)).
4. Gateway resolvers call analytics-service `/api/v1/analytics/*` via
   `HttpFinancialAnalyticsRepository`; errors map to `AnalyticsServiceUnavailable` with a
   Danish message ([gateway-service](../architecture/services/gateway-service.md)).

## Search variant (AI-20)

Chat's `transaction_search` uses analytics-service
`POST /api/v1/analytics/search/hybrid`: BM25 + pre-filtered kNN on `description_vector`,
client-side RRF, `user_id` tenant filter. Degrades to BM25-only when query embedding
fails. ChromaDB deleted 2026-07-17
([sessions/2026-07-17-loose-ends-p315-chromadb-secondsync](../sessions/2026-07-17-loose-ends-p315-chromadb-secondsync.md)).

## Why this shape (trade-offs)

- Kills the old "gateway fetches full transaction history per dashboard render" hot-path
  problem (audit CRITICAL class, voided 2026-07-13).
- Accepts **eventual consistency**: a write is visible on the dashboard only after the
  projection consumer runs; a transaction is searchable lexically before semantically.
- Accepts a **denormalized second copy** of data; self-healing full-state events are the
  consistency mechanism, not replay tooling.
- Embedding-model choice is coupled across ai-service (query side) and analytics-service
  (document side) — same model + version both sides or kNN silently degrades.

## Gotchas

- Backfill has its own gotchas (idempotency guards, ordering) — see
  [sessions/2026-07-12-es-integration-rebase](../sessions/2026-07-12-es-integration-rebase.md)
  and [plans/2026-07-11-es-analytics-integration](../plans/2026-07-11-es-analytics-integration.md).
- budget-service still computes "spent" via HTTP to transaction-service — the
  forbrug-vs-budget divergence lives there, not in the gateway (memory note; ADR-0004
  fixed only the gateway side).
