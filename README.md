
# Mai-Sale — RAG Multi-User Chat (Python)

Multi-tenant chat with history, retrieval-augmented responses (RAG), and token-based auth.

Status: Phase 1 COMPLETE • Latest: v0.1.0

---

## � Quick Start

Prereqs (use uv as the Python runner):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
```

0) Check Ollama & models:
```bash
uv run scripts/check_ollama.py --probe
```

1) Run backend (FastAPI):
```bash
uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

2) Health check (new terminal):
```bash
curl -sS -X GET http://127.0.0.1:8000/healthz -w "\nHTTP_STATUS:%{http_code}\n"
```

3) Run UI (optional):
```bash
uv run --with gradio ui/gradio_app.py
```

4) Index knowledge (optional):
```bash
uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev
```
Add `--clear` to reset the collection before indexing.

5) Test API (new terminal):
```bash
# API key (default for dev)
API_KEY="default-dev-key"

# Create a conversation
CONV=$(curl -s -X POST "http://127.0.0.1:8000/conversations" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}')
CONV_ID=$(echo "$CONV" | sed -n 's/.*"id"\s*:\s*"\([^"]*\)".*/\1/p')
echo "Conversation: $CONV_ID"

# Send a message
curl -s -X POST "http://127.0.0.1:8000/conversations/$CONV_ID/messages" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"content": "Hello, what can you tell me about Pixel phones?"}'

# Stream an answer (Server‑Sent Events)
curl -N -v -H "Accept: text/event-stream" -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -X POST "http://127.0.0.1:8000/conversations/$CONV_ID/stream" \
  -d '{"content":"test streaming"}'

# Get conversation history
curl -s -X GET "http://127.0.0.1:8000/conversations/$CONV_ID/history" \
  -H "X-API-Key: $API_KEY" | jq
```

---

## 🔧 Configuration

- OLLAMA_HOST (default: localhost)
- OLLAMA_PORT (default: 11434)
- OLLAMA_BASE_URL (overrides host/port when set)
- OLLAMA_GENERATE_URL, OLLAMA_TAGS_URL, OLLAMA_EMBEDDING_URL (full endpoints)
- DEFAULT_GENERATE_MODEL, DEFAULT_EMBEDDING_MODEL
- CHROMA_PATH (default: ./database/chroma_db)
- DATABASE_URL (default: sqlite+aiosqlite:///./database/sqlite.db)
- X_API_KEYS (comma‑separated dev keys; default includes `default-dev-key`)

Notes:
- ChromaDB persists under `database/chroma_db/`.
- `.env.local` is auto‑loaded by scripts to pick up these variables when present.

---

## � Repo Layout

- `agent/` — FastAPI app, LangGraph nodes/flows
- `docs/` — design docs (architecture, flow, retrieval, security, ops)
- `scripts/` — tools (check ollama, index knowledge, etc.)
- `knowledge/` — sample source docs
- `ui/` — Gradio client (optional)
- `database/` — local DB + Chroma persistence

---

## � More

See `docs/` for in‑depth design, operations, and testing:
- `docs/overview.md`, `docs/architecture.md`, `docs/langgraph_flow.md`, `docs/retrieval.md` …

## 📄 License

MIT — see `LICENSE`.
