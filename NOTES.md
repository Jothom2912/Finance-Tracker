# Project Notes

## Fase 2 Sanity Check Results

Date: 2026-05-06

### Setup

- Local LLM model at retrieval stage: not used directly; later Fase 3 selected `qwen3:1.7b` for generation
- Local embedding model: `embeddinggemma:latest`
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

## Fase 3 Initial RAG Smoke Test

Date: 2026-05-06

### What Worked

- The chat pipeline works end-to-end with retrieval, 4T's prompt building, local Ollama generation, and sources returned to the caller.
- `qwen3:1.7b` answered the test question correctly: "Hvad er min stoerste udgift i april 2026?" returned Husleje / Bolig at 6500 kr.
- Concise prompt context improved performance and accuracy. The LLM now receives structured source lines instead of the full embedding text with synonyms.
- The source list correctly included the retrieved April 2026 expense transactions.

### What Needed Adjustment

- `qwen3:4b` was too slow on local CPU for a reliable live demo. Even with `think=False`, reduced context, and shorter prompts it did not complete the RAG smoke test within the timeout.
- `qwen3:1.7b` is now the default MVP model because it completes the pipeline and gives a correct answer. `qwen3:4b` remains possible through `LLM_MODEL` override.
- Llama 3.2 3B was tested as an alternative, but it answered the largest-expense question incorrectly, so it was rejected.

### Decision

Use `qwen3:1.7b` as the demo-safe local LLM for MVP. Keep the prompt short, grounded, and source-based. Treat `qwen3:4b` as optional if better hardware is available.

### Model Selection Reflection

The model choice was made pragmatically based on measured hardware performance, not only expected model quality. The original plan was to use a larger Qwen 3 model because larger models are generally better at Danish and nuanced reasoning. On the development machine, however, `qwen3:4b` could not complete the RAG smoke test within the timeout, even after reducing the prompt and disabling thinking mode.

I tested smaller installed models and selected `qwen3:1.7b` as the MVP default because it completed the full RAG pipeline in about 45 seconds and answered the grounded test question correctly. The trade-off is clear: `qwen3:1.7b` is weaker than 4B/8B models for nuanced Danish and multi-step reasoning, but it is good enough for factual RAG-grounded Q&A where the answer should come directly from retrieved transactions.

The system keeps the model configurable through `LLM_MODEL`, so the delivered architecture is not locked to one model. On stronger hardware, the same code can use `qwen3:4b` or `qwen3:8b` without code changes. Before the exam demo, the same smoke-test questions should be run on the work computer to decide the final demo model.

Qwen 3 models support a thinking mode that can add significant latency before the final answer. For this use case, thinking mode is disabled with `think=False` because the task is grounded extraction and summarization from retrieved context, not open-ended reasoning. This reduced latency and made the output more direct.

### Demo Risk Mitigation

The current local demo model still takes around 45 seconds for one RAG answer. This is acceptable for a prototype but slow for a live demo. The exam demo should therefore include 3-4 prepared questions that are known to work well, while still allowing custom questions if time permits.

## Fase 4 Frontend Integration

Date: 2026-05-06

### What Was Added

- Added a new authenticated `/chat` route in the React frontend.
- Added `Finans Chat` to the main navigation.
- Added `VITE_AI_SERVICE_URL` support with default `http://localhost:8004/api/v1`.
- Added frontend API functions for `/api/v1/ingest` and `/api/v1/chat`.
- Added a chat UI with example questions, ingest button, user/assistant messages, loading state, and source details.

### Design Choices

#### Per-request timeout (lokalt fix frem for global aendring)

Local LLM generation takes 30-60 seconds depending on model and hardware, which exceeds the application's normal 30 second request timeout. Instead of raising the global timeout — which would mask real problems in other services — the shared `apiClient` was extended with a per-request `timeoutMs` parameter. Only AI chat requests use 120 seconds; all other requests keep the original 30 second timeout.

This illustrates how integrating a local LLM into an existing microservice architecture requires attention to existing conventions. The fix is scoped to the one place that needs it, preserving the safety net for everything else.

#### Progressive loading state

With 30-60 seconds of generation time, a static spinner looks like a crash. The loading indicator now progresses through three stages ("Henter relevante transaktioner...", "Bygger prompt...", "Lokal LLM genererer svar — 30-60 sekunder...") to communicate that work is happening. The messages are fake-progressive in the sense that each step does not map to a precise server event, but they turn dead wait time into perceived progress. Combined with an animated dot indicator, they make the latency feel intentional rather than broken.

#### Empty knowledge base guard

If no ingest has been run, the UI shows a warning: "Vidensbasen er tom. Tryk Opdater vidensbase for at indeksere dine transaktioner." This prevents the most likely demo failure — forgetting to index transactions before asking questions — and turns a potential error into a guided first step.

### Verification

- `npm run lint` passed.
- `npm run build` passed.
