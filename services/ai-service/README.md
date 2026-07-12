# AI Service — Finans Q&A (Streaming Pipeline)

Streaming chat service der lader brugere stille spørgsmål om deres finansielle transaktioner. Bruger en 3-trins pipeline (router → dispatcher → responder) med lokale LLM'er via Ollama og ChromaDB til semantisk søgning.

## Quick Start

```bash
cd services/ai-service
make install-deps
make dev
```

Eller via Docker Compose fra projekt-roden:

```bash
docker compose up ollama ai-service -d
# Available at http://localhost:8007
```

Forudsætter at Ollama har `qwen3:4b`, `qwen3:8b` og `bge-m3` pulled. `ollama-pull` init containeren håndterer dette automatisk.

## Port

```
8007 (host) → 8004 (container)
```

## Architecture

```
User question
    |
    v
POST /api/v1/chat/stream (SSE)
    |
    +--> Step 1: Router (qwen3:4b, constrained sampling)
    |    Klassificerer intent + period + slots
    |    → yields IntentResolvedEvent
    |
    +--> Step 2: Dispatcher
    |    Henter data fra transaction-service / monolith
    |    → yields DataReadyEvent
    |
    +--> Step 3: Responder (qwen3:8b, streaming)
    |    Genererer dansk prose-opsummering
    |    → yields ProseChunkEvent*N
    |
    v
DoneEvent (med latency metadata)
```

### Intents

| Intent | Beskrivelse | Data source |
|--------|-------------|-------------|
| `largest_expense` | Største udgift i periode | transaction-service |
| `category_breakdown` | Udgiftsfordeling per kategori | monolith dashboard |
| `transaction_search` | Semantisk søgning | ChromaDB |
| `budget_status` | Budget vs. faktisk forbrug | monolith budgets |

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/chat/stream` | JWT | SSE streaming chat pipeline |
| `POST` | `/api/v1/ingest` | JWT | Embed brugerens transaktioner i ChromaDB |
| `GET` | `/health` | None | Health check |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama server URL |
| `LLM_ROUTER_MODEL` | `qwen3:4b` | Model til intent classification |
| `LLM_RESPONDER_MODEL` | `qwen3:8b` | Model til prose generation |
| `EMBEDDING_MODEL` | `bge-m3` | Model til text embeddings |
| `TRANSACTION_SERVICE_URL` | `http://transaction-service:8002` | Transaction service URL (kun ingest) |
| `ANALYTICS_SERVICE_URL` | `http://analytics-service:8000` | Analytics-service (ES read-store) — largest_expense + category_breakdown |
| `BUDGET_SERVICE_URL` | `http://budget-service:8003` | Budget service URL |
| `CHROMADB_PATH` | `/data/chromadb` | Persistent ChromaDB storage path |
| `RETRIEVAL_TOP_K` | `10` | Antal resultater ved semantisk søgning |
| `JWT_SECRET` | — | Shared JWT secret (required) |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Allowed CORS origins |

## Models

| Purpose | Model | Config key |
|---------|-------|------------|
| Intent routing | `qwen3:4b` | `LLM_ROUTER_MODEL` |
| Prose generation | `qwen3:8b` | `LLM_RESPONDER_MODEL` |
| Text embeddings | `bge-m3` | `EMBEDDING_MODEL` |

## Known Limitations

- Semantisk søgning er svag til aggregations-queries ("total brugt på dagligvarer i april") — finder *lignende* tekster, ikke *alle* relevante. `largest_expense`/`category_breakdown` er dog eksakte (ES-aggregeringer via analytics-service, AI-19).
- Dato-parsing er begrænset til simpel dansk måned + år regex.
- Ingen chat-historik / multi-turn conversation support.
- Kategori-slot på `largest_expense` filtrerer stadig på navn klient-side (200-rækkers side) — løses af AI-21 (navn → category_id via ES taxonomy-indekset).
