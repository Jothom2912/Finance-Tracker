# Project Notes

## Current Architecture (as of 2026-05-19)

The ai-service uses a 3-step streaming pipeline: **router → dispatcher → responder**, delivered as SSE events to the React frontend.

| Component | Model | Role |
|-----------|-------|------|
| Router | `qwen3:4b` | Intent classification via constrained sampling (JSON schema) |
| Responder | `qwen3:8b` | Danish prose generation with `think=True` (thinking tokens discarded) |
| Embeddings | `bge-m3` | Semantic search via ChromaDB |

The system supports four intents: `largest_expense`, `category_breakdown`, `transaction_search` (semantic/RAG), and `budget_status`. All system prompts use the 4T's framework (TRAITS, TASK, TONE, TARGET) and are written in Danish to avoid language mixing in Qwen3's output.

This architecture replaced the original synchronous pipeline (Fase 1-4) which used a single `qwen3:1.7b` model for both classification and generation. The upgrade to separate router/responder models and SSE streaming was motivated by better hardware availability and the need for real-time token delivery to the frontend.

---

## Fase 2 Sanity Check Results (historical)

Date: 2026-05-06

### Setup

- Local embedding model: `embeddinggemma:latest` (later replaced by `bge-m3`)
- Vector store: embedded ChromaDB
- Test data: 10 transactions for user 1, 1 transaction for user 2

### What Worked

- Exact merchant queries worked well: `Netto` returned the Netto transaction as the top result.
- Category queries improved after adding category synonyms to the embedded text. `dagligvarer` returned all grocery transactions in the top 3.
- Broader semantic queries improved after synonyms. `supermarked mad indkoeb` returned Netto, Foetex, and Rema 1000 in the top 3.
- Restaurant queries worked well. `restauranter` returned Dalle Valle and McDonalds as the top 2 results.
- Date filtering worked through metadata. `april 2026` only returned April 2026 transactions, and `marts` only returned March 2026 transactions.
- Expense filtering worked through metadata. `stoerste udgift` excluded income transactions and returned Husleje as the top result.
- User isolation passed. User 1 could not retrieve user 2's transaction, and user 2 only retrieved their own transaction.

### What Needed Adjustment

- The first embedding format was too sparse for category-level questions. Adding category-related synonyms gave better ranking for `dagligvarer` and `supermarked mad indkoeb`.
- Pure vector search still returns some noise after the most relevant results. This is expected and will be handled by top-K retrieval plus prompt grounding in Fase 3.
- Aggregation questions remain a known limitation. The retriever can find relevant transactions, but it does not guarantee that all matching transactions are included unless metadata filters narrow the search enough.

### Decision

Fase 2 retrieval passes the gate. It is ready for Fase 3, where the chat endpoint will add a grounded 4T's prompt and return both answer and sources.

## Fase 3 Initial RAG Smoke Test (historical)

Date: 2026-05-06

### What Worked

- The chat pipeline works end-to-end with retrieval, 4T's prompt building, local Ollama generation, and sources returned to the caller.
- `qwen3:1.7b` answered the test question correctly: "Hvad er min stoerste udgift i april 2026?" returned Husleje / Bolig at 6500 kr.
- Concise prompt context improved performance and accuracy. The LLM now receives structured source lines instead of the full embedding text with synonyms.
- The source list correctly included the retrieved April 2026 expense transactions.

### What Needed Adjustment

- `qwen3:4b` was too slow on local CPU for a reliable live demo. Even with `think=False`, reduced context, and shorter prompts it did not complete the RAG smoke test within the timeout.
- `qwen3:1.7b` was the initial MVP model. Later replaced by `qwen3:4b` (router) and `qwen3:8b` (responder) when better hardware became available.
- Llama 3.2 3B was tested as an alternative, but it answered the largest-expense question incorrectly, so it was rejected.

### Decision

Use `qwen3:1.7b` as the demo-safe local LLM for the initial MVP. Keep the prompt short, grounded, and source-based.

### Model Selection Reflection

The model choice evolved in two stages:

**Stage 1 (Fase 3, 2026-05-06):** Selected `qwen3:1.7b` as MVP default because the development laptop could not run larger models within the timeout. The trade-off was acceptable: 1.7B is weaker at nuanced Danish but good enough for factual RAG-grounded Q&A.

**Stage 2 (streaming pipeline, 2026-05-14):** With better hardware available, the architecture was split into two models: `qwen3:4b` for intent routing (constrained sampling, low latency, `think=False`) and `qwen3:8b` for prose generation (streaming, `think=True` with thinking tokens discarded). This gave both faster classification and higher-quality Danish output.

The thinking mode decision also evolved: the router uses `think=False` because classification doesn't benefit from chain-of-thought, while the responder uses `think=True` so the model reasons internally before answering. Thinking tokens are discarded because they are in English and would violate the Danish-only contract.

All models remain configurable via environment variables (`LLM_ROUTER_MODEL`, `LLM_RESPONDER_MODEL`, `EMBEDDING_MODEL`), so the architecture is not locked to specific model sizes.

## Fase 4 Frontend Integration (historical)

Date: 2026-05-06

The initial frontend integration added a synchronous `/chat` endpoint with fake-progressive loading. This was later replaced by a real SSE streaming frontend (`useChatStream` hook + `streamChat` API) that receives typed events (`IntentResolvedEvent`, `DataReadyEvent`, `ProseChunkEvent`, `DoneEvent`) and renders tokens as they arrive.

### Design Choices (still relevant)

#### Per-request timeout

The shared `apiClient` supports per-request `timeoutMs`. Only AI requests use extended timeouts; all other services keep the 30-second default. This scoping prevents masking real problems in other services.

#### Empty knowledge base guard

If no ingest has been run, the UI warns the user and guides them to index transactions first. This prevents the most likely demo failure.
