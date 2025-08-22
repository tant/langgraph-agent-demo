# Quản lý đồng thời (Concurrency)

Ứng dụng cần xử lý nhiều user đồng thời với độ trễ thấp.

Mục tiêu: xử lý nhiều user đồng thời với latency thấp, đảm bảo tính nhất quán message↔vector và khả năng phục hồi.

### Nguyên tắc
- Ordering & idempotency: ghi message trước, trả ACK nhanh; embedding/upsert phải idempotent (key = `{message_id}#chunk_i`).
- Latency SLO: ví dụ P95 ACK < 200ms cho đường dẫn API; worker jobs có SLO riêng.

### Kiến trúc & patterns
- API layer: FastAPI (async) + `uv` (uvicorn) / gunicorn workers.
- DB: asyncpg / SQLAlchemy async + connection pool.
- Vector index: Chroma (local) — upsert từ worker.
- Worker: Celery / RQ / async background worker cho embedding/upsert.
- Xử lý message (recommended pattern):
  1. API lưu message -> trả ACK (202).
  2. Enqueue embedding job (idempotent).
  3. Worker compute embedding -> batch upsert vào Chroma; on-fail -> retry/backoff -> DLQ.
  4. Option: sync embedding for high-priority messages (tradeoff latency).

### Concurrency controls
- Rate limiting: per-user + global (Redis + middleware). In development, run without Redis (use in-process rate limiter or lower limits); Redis required in production for distributed rate-limiting.
- Locks: Redis locks (production) hoặc optimistic concurrency when Redis not available in dev.
- Backpressure: khi queue_length cao, trả 429 hoặc giảm chức năng realtime (ví dụ disable sync embedding).

### Operational defaults (ví dụ khởi điểm)
- SQL pool size: 10
- Celery workers: 4
- Embedding worker concurrency: 2
- Rate limit: 5 req/s per user
- Retry policy: exponential backoff, max 3 attempts -> DLQ

### Observability & health
- Traces/logs: include request_id, conversation_id; structured JSON logs.
- Metrics: embedding_latency, vector_query_time, queue_length, db_conn_usage, error_rate.
- Alerts: queue_length > threshold, DLQ rate > 0, embedding failure rate spike.
- Graceful shutdown: drain queues, finish in-flight jobs or move them to DLQ.

### Testing checklist
- Unit: idempotent upsert logic, lock handling.
- Integration: end-to-end message -> worker -> vector exists in Chroma.
- Load: simulate concurrent users (e.g., 100 concurrent, validate P95 latencies and queue growth).
- Chaos: worker restarts, Redis outage, and ensure DLQ behavior.

### Quick checklist for devs
- Initialize heavy clients per-process (Chroma/Ollama clients) to avoid cross-thread issues.
- Ensure upsert keys are idempotent.
- Add DLQ and clear retry policy.
- Export metrics and wire basic alerts.
