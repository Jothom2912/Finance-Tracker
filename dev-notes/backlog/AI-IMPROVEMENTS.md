# AI-service improvement backlog — RAG, router, responder

Companion to [FEATURES.md](FEATURES.md) (F2-04 search UI, F2-06 chat intents) and [BACKLOG.md](BACKLOG.md) (P3-04 event-driven vector sync, M24 slot bugs). IDs `AI-xx` are stable.

Current pipeline (see [architecture/services/categorization-and-ai-services.md](../architecture/services/categorization-and-ai-services.md)): router qwen3:4b (4 intents, constrained JSON) → dispatcher (gateway/tx/budget HTTP or ChromaDB search, bge-m3, user_id-filtered) → responder qwen3:8b (Danish prose, SSE). Known weaknesses on record (NOTES.md sanity checks): **aggregation questions unreliable** (vector search can't guarantee completeness), **noise after top results**, slots (`category`/`amount_*`) defined but never emitted by the router (unreachable filter code, audit M24).

**Ground rule for all of this: build AI-01 (eval harness) first.** Every other item claims "better retrieval/answers" — without a golden set none of those claims are testable, and prompt/model tweaks will regress silently.

## A1 — Foundations & quick wins

| ID | Idea | What & why | Builds on | Effort | Status |
|----|------|-----------|-----------|--------|--------|
| AI-01 | **Retrieval + answer eval harness** | Golden set of ~50 Danish Q/A pairs over a fixture dataset (exact-merchant, category, aggregation, date-range, negation cases). Metrics: recall@k / MRR for retrieval, numeric-correctness for answers. Runnable via pytest marker; report in CI. Fix/absorb the broken `scripts/sanity_check_retrieval.py` | The old sanity-check scripts + NOTES.md test cases are half of the golden set already | M | open |
| AI-02 | **Wire metadata self-query (fix dead slot path)** | Teach the router prompt to actually emit `category`, `amount_min/max`, `is_expense` slots (few-shot examples); fix the `amount_min` clobbers `amount_max` bug (M24); translate slots → ChromaDB `where` filters. Turns "udgifter over 500 kr i marts" from fuzzy search into a filtered query | The whole slot→filter translation layer already exists, unreachable — this is activation, not construction | S | open |
| AI-03 | **Aggregation router guard** | Aggregate questions ("hvor meget brugte jeg på…", "i alt", "sum") must NEVER be answered from top-K vectors — route to structured data (gateway/tx endpoints compute the sum) and let the LLM only phrase it. Add an `aggregation` intent or slot; documented known limitation becomes a solved class | Dispatcher already has structured paths for 3 of 4 intents — this extends the routing rule | S | open |
| AI-04 | **Grounded citations in UI** | Return source transactions alongside the streamed answer (data is already in the `data_ready` SSE event) and render "baseret på disse transaktioner" in ChatPage. Trust + debuggability for free | SSE event model already carries the data; frontend chat slice is the best-tested code in the app | S | open |
| AI-05 | **Numeric guardrail** | Compute all sums/counts in code, inject as explicit FACTS block in the responder prompt, and post-check streamed prose for amounts that don't appear in the context (flag/correct suffix event). LLMs must never do arithmetic | Pipeline already formats a text context block; extends it | S | open |

## A2 — Retrieval quality (the RAG ladder, in order of expected ROI)

| ID | Idea | What & why | Builds on | Effort | Status |
|----|------|-----------|-----------|--------|--------|
| AI-06 | **Hybrid lexical + vector search** | Merchant names are exact-match-shaped ("Netto", "McDonalds") — pure vectors add noise. Combine ChromaDB vector results with lexical matching (`where_document` contains / simple BM25 over descriptions) via reciprocal-rank fusion | ChromaDB supports `where_document`; descriptions already normalized at ingest | M | open |
| AI-07 | **Reranking** | Cross-encoder rerank of top-20 → top-5 (e.g. `bge-reranker-v2-m3`, same family as the embedder, runs local). Directly attacks the documented "noise after the most relevant results" | Ollama runtime already in the stack; retrieval interface has one call site | M | open |
| AI-08 | **Query rewriting** | Rewrite colloquial Danish queries into retrieval-friendly form + synonyms *at query time* (router already makes an LLM call — piggyback rewriting into the same structured output; zero extra latency). Ingest-side synonyms exist; query side is the missing half | Router's constrained-JSON output just gains a `search_query` field | S | open |
| AI-09 | **Multi-granularity index** | Embed monthly-summary docs and category-summary docs alongside per-transaction docs (typed metadata). Comparison/trend questions retrieve summaries; detail questions retrieve transactions. Complements AI-03 for the aggregation gap | Ingest already builds Danish prose docs; add two more doc builders + a `doc_type` filter | M | open |
| AI-10 | **Multi-hop retrieval** *(user idea)* | Decompose complex questions into sequential retrieve→reason→retrieve steps: "brugte jeg mere på mad i marts end april?" → retrieve/aggregate March → April → compare; "hvad kostede min største vane sidste år?" → find recurring merchant → then fetch its yearly total. Implement as a bounded agentic loop in the dispatcher (max 3 hops): router emits a plan OR responder-as-planner requests a follow-up query via structured output; each hop can hit vectors or structured endpoints. Surface hops as SSE progress events (the event model supports adding a `hop` event type) | Discriminated-union SSE events + typed dispatcher make a loop insertable without rearchitecting; AI-03/AI-09 give the per-hop tools | L | open |
| AI-11 | **Incremental/embedding-cache ingest** | Content-hash per doc; re-ingest embeds only new/changed transactions and deletes removed ones. Kills the O(N)-every-click cost and the ghost-data problem; prerequisite-sharing with P3-04 (event-driven sync — same doc-builder code) | Deterministic doc ids (`user:{uid}:txn:{tid}`) already exist — hashing slots in cleanly | M | open |

## A3 — Router, responder & conversation

| ID | Idea | What & why | Builds on | Effort | Status |
|----|------|-----------|-----------|--------|--------|
| AI-12 | **Multi-turn context** | Follow-ups ("og i april?", "kun MobilePay?") fail today — pipeline is stateless per question. Condense last N turns into a context line for the router (coreference: inherit intent/period/slots unless overridden). Chat history already lives in the frontend reducer — send it (or keep a server-side session) | `chatReducer` history + router prompt change; no new storage needed if history rides the request | M | open |
| AI-13 | **Router confidence + clarify** | Below a confidence threshold, ask ONE clarifying question (new SSE `clarify` event) instead of silently falling back to `transaction_search`. Wrong-intent answers are worse than a question | Router already returns a confidence float that's currently unused past logging | S | open |
| AI-14 | **Cheap intent pre-classifier** | bge-m3 embedding + tiny logistic/centroid classifier for the 4-6 intents; call the LLM router only for slot extraction or low-margin cases. Cuts ~1-2s p50 latency and Ollama load | Embeddings infra shared with retrieval; AI-01 provides the labeled data | M | open |
| AI-15 | **Use the discarded thinking tokens** | Responder runs `think=True` and throws the reasoning away. Either turn thinking off (latency win) or use it: self-check pass ("do the numbers in my draft match the FACTS block?") before streaming. Measure both against AI-01 | One flag + optional check step | S | open |
| AI-16 | **Feedback signal** | 👍/👎 per answer, stored with question/intent/retrieved ids. Feeds AI-01's golden set growth and flags bad intents/retrievals in the wild | Notification/UI patterns exist; tiny table in ai-service | S | open |
| AI-17 | **Proactive insights** | Monthly digest generated through the same pipeline ("dit madforbrug steg 18%…"), delivered via notification service. Chat becomes push, not only pull | F1-01 notifications + F2-06 intents; AI-05 guardrails mandatory here | M | open |
| AI-18 | **ChromaDB server mode ADR** | Embedded PersistentClient caps ai-service at 1 replica and couples storage to the pod. Decide: chroma server container vs pgvector-in-Postgres (fits database-per-service house style). Write the ADR before any scaling work | Audit M24; infra patterns for both exist in-repo | S (ADR) | open |

## Sequencing

```
AI-01 eval harness  ──►  gate for everything below
Wave A (activation, days):    AI-02, AI-03, AI-04, AI-05, AI-08, AI-13, AI-15
Wave B (quality, per-item):   AI-06 → AI-07 → AI-09 → AI-11   (measure each against AI-01)
Wave C (capability):          AI-12 → AI-10 multi-hop (needs A-wave tools + B-wave retrieval)
Continuous:                   AI-16 feedback; AI-18 ADR before any multi-replica plan; AI-14 when latency hurts; AI-17 after F1-01
```

Multi-hop (AI-10) deliberately comes late: hops multiply whatever retrieval quality you have — 3 hops over noisy retrieval compounds noise, 3 hops over AI-06/07/09-grade retrieval compounds signal.

## Parked (with reason)

- **HyDE / fancy query embedding tricks** — try only if AI-06/07/08 leave measurable recall gaps on the eval set; usually dominated by reranking at this corpus size.
- **Fine-tuning models** — corpus is per-user and small; prompt + retrieval engineering wins here. Revisit if AI-16 accumulates real training data.
- **LLM-tier categorization via ai-service** — belongs to categorization-service (F1-06), keep the boundary.
