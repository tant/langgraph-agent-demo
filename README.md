
# Mai-Sale — Retrieval-Augmented Multi-User Chat (Python)

**Multi-tenant chat with conversation history, retrieval-augmented responses (RAG), and simple token-based auth.**

---

## 📚 Project Index & Quick Links

- **Docs:** See `docs/` for detailed design notes. Key files:
  - [`docs/overview.md`](docs/overview.md): Project overview & assumptions
  - [`docs/langgraph_flow.md`](docs/langgraph_flow.md): LangGraph flow & AgentState
  - [`docs/architecture.md`](docs/architecture.md): System architecture
  - [`docs/data_model.md`](docs/data_model.md): Data model & chunking
  - [`docs/retrieval.md`](docs/retrieval.md): Retrieval strategy
  - [`docs/concurrency.md`](docs/concurrency.md): Concurrency & operational defaults
  - [`docs/security.md`](docs/security.md): Security & privacy
  - [`docs/testing.md`](docs/testing.md): Testing guide
  - [`docs/ops.md`](docs/ops.md): Operations & runbook
  - [`docs/run_local.md`](docs/run_local.md): Run locally

**Tech stack:** Python 3.10+, Ollama (`gpt-oss` for generation, `bge-m3` 1024-d for embeddings), FastAPI, LangGraph, ChromaDB (PersistentClient local), Postgres/SQLite, Gradio UI (optional)

**Repo structure:**
- `agent/` — FastAPI app, LangGraph flows, nodes
- `database/` — local DB + Chroma persistence
- `docs/` — detailed docs
- `scripts/` — indexer, backups, maintenance scripts
- `knowledge/` — source documents to index
- `ui/` — optional Gradio client

---

## 🚀 Quick Start

Use uv for Python runtime and scripts. If you haven't installed uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
```

1. **Run backend:**
	```bash
	uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
	```
2. **Run UI (optional):**
	```bash
	uv run --with gradio ui/gradio_app.py
	```
3. **Index knowledge (optional):**
	```bash
	uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev
	```

---

## 🛠️ Operational Notes

- To index knowledge: `uv run --no-project --with chromadb --with requests --with tqdm --with python-dotenv scripts/index_knowledge.py --source knowledge/ --collection conversations_dev`
- ChromaDB sẽ lưu tự động vào thư mục `database/chroma_db/` (PersistentClient)
- Backup Chroma folder cùng DB metadata nếu dùng local.
- See `docs/` for detailed design, security, and operational notes.

---

## 🐍 Using `uv` (Python & scripts)

Key patterns (see the [uv scripts guide](https://docs.astral.sh/uv/guides/scripts/)):

```bash
# Run a script with inline metadata (PEP 723)
uv run scripts/index_knowledge.py

# Run uvicorn
uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000

# Add temporary dependencies
uv run --with rich some_script.py

# If inside a project but the script doesn't depend on it
uv run --no-project tools/one_off.py
```

---

## 🌐 Environment Variables

- `OLLAMA_HOST` (default: localhost)
- `OLLAMA_PORT` (default: 11434)
- `CHROMA_PATH` (default: ./database/chroma_db)
- `DATABASE_URL` (sqlite:///./database/sqlite.db or Postgres URL)
- `REDIS_URL` (optional — production only; local dev can run in no-Redis mode)
- `X_API_KEY_ADMIN` (admin token for management endpoints)

Ollama commonly runs locally — TLS to Ollama is optional when Ollama is localhost and not network-exposed.

---

## 🏗️ Architecture

- **API (FastAPI):** Receives messages, stores them, enqueues embedding jobs, and exposes conversation/history endpoints.
- **Workers:** Background workers (Celery/RQ or async tasks) compute embeddings and upsert into ChromaDB.
- **Vector store:** ChromaDB (PersistentClient lưu local tại `./database/chroma_db/`).
- **LLMs/Embeddings:** Ollama — `gpt-oss` for generation, `bge-m3` (1024-d) for embeddings.
- **UI:** Gradio thin client that calls the REST API.

---

## 🔍 Retrieval Policy
1. Use same-conversation chat history as context.
2. If coverage/confidence insufficient, expand to the knowledge base (Chroma) using `bge-m3` embeddings and vector search.
3. Fetch a larger candidate set (e.g., N=20), re-rank by vector score + heuristics (freshness, same-conversation boost), and select top-K (default K=3, expand up to 10 if budget allows).

---

## 🗃️ Data Model
- `conversations(id UUID)`
- `messages(id UUID, conversation_id, sender, text, tokens_estimate, metadata)`
- Mapping: `messages.id` → Chroma vector id; chunking: 200–512 tokens; chunk key `{message_id}#chunk_{i}`

---

## ⚙️ Operational Defaults
- SQL pool: 10
- Celery workers: 4
- Embedding worker concurrency: 2
- Rate limit: 5 req/s per user
- Retry policy: exponential backoff, max 3 attempts → DLQ
- SLO example: P95 request ACK < 200ms

---

## 🧪 Dev vs Production
- **Dev:** SQLite, local Chroma, Ollama on localhost, Redis optional (use in-process fallbacks)
- **Prod:** Postgres (+pgvector) recommended, Chroma persistent storage, Redis for distributed locks/rate-limit/queue coordination, KMS/Vault for secrets, TLS/mTLS as needed

---

## 🧑‍💻 Testing & CI
- Unit tests: pytest (mock Ollama/Chroma clients)
- Integration: testcontainers or in-memory Chroma + SQLite for CI
- Load tests: k6; example target: 100 concurrent users, P95 < 200ms

---

## 🛡️ Security Notes
- Token-based auth via `X-API-Key`; support revocation and short-lived tokens for sensitive ops
- Avoid storing PII in embeddings; mask/redact sensitive fields
- Use KMS/Vault for prod secrets; run SCA in CI

---

## 📖 More Details
See the `docs/` folder for in-depth documentation on all aspects of the project.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
