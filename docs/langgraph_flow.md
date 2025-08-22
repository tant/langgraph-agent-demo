# Luồng LangGraph & Thiết kế Agent (gọn, đủ ý)

Tài liệu mô tả flow LangGraph, các node chính và các quyết định triển khai (ChromaDB local, bge-m3 1024-d, backend tách Gradio).

## Luồng tổng thể (rút gọn)
0. START -> 1. Nhận câu hỏi -> 2. Phân loại (retrieve? trả lời ngay?)
- Nếu cần retrieve -> 3. Retrieve (ChromaDB) -> 4. Trả lời (LLM) -> 5. Hỏi user có muốn tiếp?
- Nếu không cần retrieve -> 4. Trả lời -> 5. Hỏi user có muốn tiếp?
- Nếu dừng -> 6. END

## Nodes (tóm tắt hành động)
- Node 1 (Nhận câu hỏi): xác thực token (`X-API-Key`), tạo/đảm bảo conversation, lưu message raw vào DB (message_id).
- Node 2 (Phân loại): quyết định truy hồi dựa trên question + chat_history + heuristic.
- Node 3 (Retrieve): truy Chroma (filter theo conversation/user), trả về top-K, re-rank theo freshness/same-conversation.
- Node 4 (Trả lời): build prompt (history + retrieved), gọi LLM (`gpt-oss`) để sinh response, lưu response.
- Node 5 (Hỏi tiếp): xác định ý định user -> quay lại Node 1 hoặc END.
- Node 6 (END): mark conversation inactive, schedule retention/cleanup.

## AgentState (rút gọn)
- conversation_id
- user_id
- chat_history (list of {id, role, content, created_at})
- last_updated
- metadata (dict)

> Ghi chú: Message id dùng làm reference để upsert vectors vào Chroma (vector id = message_id).

## Persistence & Chroma mapping
- Messages (text + metadata) lưu trong primary DB; vectors lưu/được index trong ChromaDB (`./database/chroma_db/`).
- Mapping: `messages.id` -> chroma vector id. Dimension: 1024 (bge-m3).
- Upsert batch, idempotent; delete vectors khi xóa message/conversation.

## Embedding strategy
- Model: `bge-m3` (1024-d) via Ollama.
- Chunking: 200–512 tokens nếu lớn; chunk id = `{message_id}#chunk_{i}`.
- Prefer enqueue embedding job (worker) để giảm latency request path; có option sync for critical messages.

## Node implementation notes
- Implement nodes as async functions; avoid blocking I/O in node body.
- Use background queue (Celery/RQ/async tasks) cho embedding/upsert.
- Nodes return updated AgentState + useful metadata (retrieved segments, errors).

## Error & Observability
- Jobs (embedding/upsert) phải có retry/backoff; nếu thất bại, mark message.metadata['embed_failed']=true.
- Gắn `request_id` và `conversation_id` cho mỗi request; export traces/logs (structured JSON) để debug.

## API contract (gợi ý, súc tích)
- POST /conversations -> tạo conversation (201)
- POST /conversations/{id}/messages -> ghi message + trả ACK (202 Accepted). Embedding xử lý async; response assistant được lưu khi hoàn tất (query via history endpoint or websocket/stream).
- GET /conversations/{id}/history -> trả về history (messages + assistant responses)
- POST /admin/index -> trigger indexing of `knowledge/` (authenticated)

## Quick test notes
- Expect POST /messages to be fast (ack), embedding/upsert happens in background.
- For realtime demo, optionally compute embedding sync (tradeoff latency).

## Assumptions (env)
- OLLAMA_HOST (default: localhost)
- OLLAMA_PORT (default: 11434)
- CHROMA_PATH (default: ./database/chroma_db)
- DATABASE_URL (sqlite:///./database/sqlite.db or Postgres URL)
- REDIS_URL (optional)
	- Note: Redis is optional for local dev; in production enable Redis for caching, locks, and distributed rate-limiting.
