---
title: AI-20 embedding writer lives in analytics-service as a separate consumer on its own queue
date: 2026-07-13
status: accepted
supersedes: null
promoted-to-adr: null
---

# AI-20 embedding writer lives in analytics-service as a separate consumer on its own queue

## Decision

The `description_vector` (bge-m3, 1024 dims) on the ES `transactions` index is written by
a **second consumer inside analytics-service**, bound to `transaction.*` on its **own
queue** (`analytics.embeddings`, own DLQ). It calls Ollama `/api/embed` and issues an ES
**partial update** of only the `description_vector` field. The existing projection
consumer and its queue are untouched.

## Context

AI-20 (plan [2026-07-12-ai-service-es-chat](../plans/2026-07-12-ai-service-es-chat.md),
step 8) replaces ChromaDB with ES hybrid BM25+kNN search, which requires a dense vector
per transaction document. Someone has to compute embeddings on every
`transaction.created/updated` event and get them into ES. Forces:

- ADR-0004: analytics-service owns all writes to the ES read-store.
- Ollama is slow (~0.4 s/tx measured) and can be down — embedding must never stall or
  poison the core projection path that the dashboard depends on.
- The projection consumer (`app/workers/projection_consumer.py`) already has the needed
  machinery: topic-exchange bindings via `QUEUE_BINDINGS`, per-queue DLQ, idempotent
  full-state upserts (self-healing consumer pattern per CLAUDE.md).

## Alternatives considered

- **Embed inside the main projector** (same consumer, same queue) — rejected: couples
  core projections to Ollama uptime and latency; an Ollama outage would back up the queue
  that keeps `transactions/accounts/goals` fresh, i.e. the chat feature could break the
  dashboard.
- **ai-service writes vectors to ES directly** — rejected: breaks store-per-service
  ownership (ADR-0004); two writers to one index reintroduces exactly the sync/ownership
  ambiguity the read-store cutover removed. ai-service still embeds the *query* at search
  time (it owns Ollama for chat), which is fine — queries are ephemeral, documents are
  state.
- **Batch/cron re-embed instead of event-driven** — rejected as primary path: reintroduces
  the ChromaDB staleness problem (P3-04, "ghost data") that AI-20 exists to kill. A batch
  variant of `app/tools/backfill.py` is still used once for the historical backfill.

## Consequences

- Easier: DLQ/retry, monitoring and idempotency piggyback the existing consumer pattern —
  one new entry in `QUEUE_BINDINGS`-style setup, not a new deployment.
- Easier: Ollama outage degrades gracefully — vectors lag or go to DLQ, core projections
  unaffected; the hybrid endpoint must therefore tolerate missing vectors (degrade to
  BM25-only), which becomes an explicit requirement on the AI-20 search endpoint.
- Harder: analytics-service gains an Ollama dependency (config: `OLLAMA_BASE_URL`,
  `EMBEDDING_MODEL`) — a second service now needs the embedding model pulled, and
  embedding-model choice is coupled across ai-service (query side) and analytics-service
  (document side). Same model + version must be used on both sides; drift here silently
  degrades kNN quality. Mitigation: both read the same env var names via compose/k8s
  shared config.
- Eventual consistency between document indexing and vector availability: a transaction
  is searchable lexically before it is searchable semantically. Accepted — hybrid RRF
  still surfaces it via BM25.
