# Kiến trúc (ngắn gọn và đủ ý)

Mục tiêu: mô tả súc tích các thành phần chính, luồng dữ liệu và các quyết định triển khai.

## Quick run (1-liner)
- Run backend: `uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000` (run uvicorn via uv)

## Thành phần chính
- Backend: FastAPI (async) — tách biệt, chịu trách nhiệm auth, session, LangGraph orchestration, gọi Ollama và ChromaDB.
- UI: Gradio (thin client) — chạy riêng, gọi REST API của backend (khuyến nghị cho prod).
- Orchestrator: LangGraph xử lý flow/prompt building.
- Vector store: ChromaDB (local) — path `./database/chroma_db/`.
- Embeddings: Ollama `bge-m3` (1024-d); Generation: Ollama `gpt-oss`.
- Persistence: Postgres (prod) / SQLite (dev) cho users, conversations, messages metadata.
- Workers: background queue (Celery/RQ/async tasks) cho embedding/upsert và công việc nặng.
- Cache: Redis (optional) cho cache, locks, rate limiting.
	- Note: Redis is optional for local development; in production enable Redis for cache, locks, and rate-limiting.

## Luồng xử lý (rút gọn)
1. Client gửi message -> Backend (POST /conversations/{id}/messages).
2. Backend: xác thực token (`X-API-Key`), lưu message, trả ACK (202).
3. Backend enqueue embedding job -> worker gọi Ollama `bge-m3` -> upsert vào Chroma.
4. Trả lời: retriever -> LangGraph prompt -> Ollama `gpt-oss` -> lưu và trả response.

## UI (ngắn)
- Khuyến nghị: Gradio làm frontend độc lập (thin client) gọi REST API; trong dev có thể chạy local để demo nhanh.

## Vector store (ChromaDB)
- Local path: `./database/chroma_db/`.
- Mapping: `messages.id` ↔ chroma vector id; embedding dim = 1024.
- Upsert: batch, idempotent (key = `{message_id}#chunk_{i}`).
- Delete: xóa vector khi message/conversation bị xóa.

## Authentication & Env vars (tối thiểu)
- Auth: opaque token via header `X-API-Key` (simple token -> user_id lookup).
- Env (min): `OLLAMA_HOST` (default: localhost), `OLLAMA_PORT` (11434), `CHROMA_PATH` (./database/chroma_db), `DATABASE_URL`, `REDIS_URL` (optional).

	- Note: `REDIS_URL` may be left unset in development. The system supports a no-Redis mode with in-process fallbacks for caching/locks; enable Redis in production for distributed correctness.

## Observability & retry
- Gắn `request_id` và `conversation_id` lên logs/traces; use structured JSON logs.
- Jobs (embedding/upsert) có retry/backoff; nếu fail, mark `message.metadata['embed_failed']=true` để hỗ trợ retry manual.

## Backup & restore
- Snapshot `./database/chroma_db/` and DB metadata regularly (daily/weekly as needed); test restore.

## Scale & ops (tóm tắt)
- Scale backend and workers horizontally; use load balancer + shared Redis/Postgres.
- Monitor: request latency, embedding time, vector query time, queue length.

## Quyết định đã chốt
- Vector store: ChromaDB (local)
- Embedding: bge-m3 (1024-d)
- Generation: gpt-oss (Ollama)
- Backend/API: FastAPI (tách Gradio)
- Auth: simple token via `X-API-Key`
