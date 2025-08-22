# Tổng quan dự án

Mục tiêu: xây dựng một ứng dụng chat đa người dùng (multi-user chat) dùng LangGraph và Ollama để xử lý ngôn ngữ tự nhiên, có lưu lịch sử hội thoại và hỗ trợ retrieval-augmented responses.

Tính năng chính:
- Hỗ trợ nhiều user đồng thời.
- Lưu lịch sử hội thoại theo conversation/session.
- Tạo embedding cho đoạn hội thoại và index vào ChromaDB (vector store local) để truy hồi.
- Sử dụng Ollama với model `gpt-oss` cho generation và `bge-m3` (1024-d) cho embeddings.
- Chiến lược retrieval (tóm tắt): ưu tiên lấy context từ same-conversation (chat history); nếu coverage/confidence không đủ, mở rộng truy vấn sang knowledge base (ChromaDB) dùng embeddings `bge-m3` và áp dụng vector search + re-rank (vector score + heuristics + optional lexical/BM25).
- Backend FastAPI tách biệt; Gradio làm frontend gọi REST API.

Giả định ban đầu:
- Phát triển bằng Python (3.10+).
- Dùng `uv` để chạy server (bạn đã cài sẵn).
- Ollama đã được cài và model tương ứng đã được tải trên host.

Xem các phần chi tiết khác để biết kiến trúc, mô hình dữ liệu, chiến lược retrieval, vận hành và bảo mật.

## UI (Frontend)

- UI dự kiến dùng: Gradio — một framework Python đơn giản để nhanh chóng tạo giao diện chat/web UI cho mô hình.
- Mục đích: cung cấp giao diện web nhẹ để user gửi message, xem phản hồi, và quản lý session (tạo, xóa, export).
- Tích hợp:
  - Gradio hoạt động như thin client: gọi REST API của backend FastAPI (khuyến nghị cho cả dev/prod để nhất quán mô hình triển khai).

## Lợi ích
- Triển khai nhanh giao diện thử nghiệm.
- Hỗ trợ interactivity (buttons, file upload) và dễ kết nối với backend qua REST để demo nhanh.

## Lưu ý
- Gradio mặc định không phải là load-balanced production-ready frontend khi có hàng trăm kết nối; cần đặt phía trước bằng một reverse proxy hoặc tách frontend/back-end để scale.

## Quick start
- Run backend (FastAPI):

```bash
uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

- Run UI (Gradio client):

```bash
uv run --with gradio ui/gradio_app.py
```

## Env vars (minimum)
- OLLAMA_HOST (default: localhost)
- OLLAMA_PORT (default: 11434)
- CHROMA_PATH (default: ./database/chroma_db)
- DATABASE_URL (e.g., sqlite:///./database/sqlite.db or Postgres URL)
- REDIS_URL (optional, for cache/queue)
  - Note: Redis is optional in development; enable Redis in production for cache, locks, and rate-limiting.

## Quick API example
Send a message (replace values):

```bash
curl -X POST "http://localhost:8000/conversations/<conversation_id>/messages" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-token" \
  -d '{"content":"Hello"}'
```

## See also
- `docs/architecture.md` — Kiến trúc ngắn gọn
- `docs/langgraph_flow.md` — Luồng LangGraph & AgentState
- `docs/run_local.md` — Hướng dẫn chạy cục bộ chi tiết
- `docs/data_model.md` — Mô hình dữ liệu & mapping tới ChromaDB
- `docs/retrieval.md` — Chiến lược retrieval
