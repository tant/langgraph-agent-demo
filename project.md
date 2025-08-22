# Project index & quick links

This repository's documentation and quick-start live in `README.md` (root) and the `docs/` folder. Use `README.md` for a developer/operator quick-start and `docs/` for detailed design notes.

Docs (short index):
- `docs/overview.md` — project overview & assumptions
- `docs/langgraph_flow.md` — LangGraph flow & AgentState
- `docs/architecture.md` — system architecture
- `docs/data_model.md` — data model & chunking
- `docs/retrieval.md` — retrieval strategy
- `docs/concurrency.md` — concurrency & operational defaults
- `docs/security.md` — security & privacy
- `docs/testing.md` — testing guide
- `docs/ops.md` — operations & runbook
- `docs/run_local.md` — run locally

Quick summary (see `README.md` for details):
- Language: Python 3.10+
- LLM provider: Ollama (`gpt-oss` for generation, `bge-m3` 1024-d for embeddings)
- Runtime: `uv`/uvicorn
- Persistence: Postgres + pgvector (prod) / SQLite (dev)
- Vector store: ChromaDB (local)
- UI: Gradio thin client (optional `ui/` folder)

Expected layout (high level):
- `agent/` — agent code (FastAPI app, LangGraph flows, nodes)
- `database/` — local DB + Chroma persistence (`./database/chroma_db/`)
- `docs/` — detailed docs (this folder)
- `scripts/` — indexer, backups, maintenance scripts
- `knowledge/` — source documents to index
- `ui/` — optional Gradio client

Operational hint:
- Index knowledge: `uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev`
- Backup Chroma folder together with DB metadata.
- `docs/` — chứa tài liệu chi tiết dự án (đã tạo nhiều file ở đây).
