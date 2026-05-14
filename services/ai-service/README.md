# AI Service — Finans Q&A (RAG)

RAG-based chat service that lets users ask questions about their financial transactions. Uses a local LLM (Qwen 3 via Ollama) with ChromaDB for vector retrieval and 4T's prompt engineering.

## Quick Start

```bash
cd services/ai-service
make install-deps
make dev
```

Or via Docker Compose from the project root:

```bash
docker compose up ollama ai-service -d
# Available at http://localhost:8007
```

First-time setup pulls ~2 GB of model data (`qwen3:1.7b` + `embeddinggemma:latest`). This takes 5-15 minutes depending on your connection. The `ollama-pull` init container handles this automatically.

## Port

```
8007 (host) → 8004 (container)
```

The host port was moved from 8004 to 8007 to make room for account-service on port 8004. The container still listens on 8004 internally.

## Architecture

```
User question
    |
    v
POST /api/v1/chat
    |
    +--> Pre-process (parse date/category hints)
    |
    +--> Retrieve (embed question, search ChromaDB with user_id + metadata filters)
    |
    +--> Build prompt (4T's template + retrieved transactions)
    |
    +--> Generate (Ollama qwen3:1.7b)
    |
    v
Answer + sources
```

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/ingest` | JWT | Fetch and embed user's transactions into ChromaDB |
| `POST` | `/api/v1/chat` | JWT | Ask a question about your transactions |
| `GET` | `/health` | None | Service health check |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL (`docker-compose` overrides to `http://host.docker.internal:11434`) |
| `LLM_MODEL` | `qwen3:1.7b` | Model for answer generation |
| `EMBEDDING_MODEL` | `embeddinggemma:latest` | Model for text embeddings |
| `TRANSACTION_SERVICE_URL` | `http://transaction-service:8002` | Transaction service URL |
| `CHROMADB_PATH` | `/data/chromadb` | Persistent ChromaDB storage path |
| `RETRIEVAL_TOP_K` | `30` | Number of transactions to retrieve |
| `JWT_SECRET` | — | Shared JWT secret (required) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |

## Models

| Purpose | Model | Size |
|---------|-------|------|
| Answer generation | `qwen3:1.7b` | ~1.4 GB |
| Text embeddings | `embeddinggemma:latest` | ~621 MB |

`qwen3:4b` can be used by overriding `LLM_MODEL`, but local CPU testing showed it was too slow for a reliable live demo on this machine.

## Known Limitations

- Vector search is weak at aggregation queries ("total spent on groceries in April") because it finds *similar* texts, not *all* relevant ones. Metadata filtering helps but does not fully solve this.
- Date parsing is limited to simple month name + year regex matching.
- No chat history / multi-turn conversation support in MVP.
