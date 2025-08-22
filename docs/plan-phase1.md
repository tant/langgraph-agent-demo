# Phase 1 Plan — MVP RAG Chat (Backend + Retrieval + Minimal UI)

Mục tiêu: Hoàn thiện một phiên bản MVP end-to-end của hệ thống chat đa người dùng với RAG, có thể chạy local, có test cơ bản, và tài liệu vận hành tối thiểu.

Thời gian gợi ý: 1–2 tuần (tùy nguồn lực). Có thể chạy theo mốc M1 → M5 dưới đây.

---

## Phạm vi (Scope)
- Backend FastAPI (auth `X-API-Key`, conversations/messages, LangGraph flow cơ bản)
- Tích hợp Ollama (gpt-oss generate, bge-m3 embeddings)
- Retrieval với ChromaDB (PersistentClient, filters cơ bản)
- Lưu lịch sử hội thoại (SQLite dev) + ánh xạ vector (Chroma)
- UI mỏng Gradio gọi REST API (tối thiểu)
- Script vận hành: kiểm tra Ollama, index knowledge (đã có)
- Test: unit + smoke integration
- Tài liệu: README, run_local, ops (đã cập nhật thêm scripts) + phần Troubleshooting ngắn

Ngoài phạm vi (Phase 2+): RBAC nâng cao, Redis distributed locks/rate-limit, Postgres/pgvector, Websocket streaming, CI/CD đầy đủ, multi-tenant isolation nâng cao, content safety advanced.

---

## Giả định & Tiền đề
- Python 3.12 với `uv` khả dụng.
- Ollama chạy local, có models `gpt-oss` và `bge-m3` (có thể kiểm tra bằng `scripts/check_ollama.py`).
- ChromaDB dùng local persistent path `./database/chroma_db/`.
- Dev DB: SQLite (file trong repo), no-Redis mode cho local.

---

## Mốc (Milestones)
- M1: Khởi tạo Backend skeleton + Health + Auth cơ bản
- M2: Data layer (SQLite) + endpoints conversations/messages
- M3: LangGraph flow + tích hợp Ollama + Retrieval Chroma
- M4: UI Gradio tối thiểu + Index knowledge hoàn tất
- M5: Tests (unit + smoke) + tài liệu + kiểm tra chất lượng (quality gates)

---

## Công việc chi tiết (Tasks) — với Acceptance Criteria (AC)

### T-01 Backend Skeleton (FastAPI)
- Thiết lập `agent/main.py` với FastAPI app, health `/healthz`, version `/version`.
- Middleware đọc `X-API-Key` (dev: danh sách token hợp lệ cấu hình tĩnh qua env).
- Cấu hình ENV: `OLLAMA_HOST/PORT`, `CHROMA_PATH`, `DATABASE_URL`.
AC:
- Chạy `uv run uvicorn agent.main:app ...` trả 200 cho `/healthz`.
- Request không có `X-API-Key` bị 401 trừ `/healthz`.

### T-02 Data Model (SQLite dev)
- Tạo bảng `conversations`, `messages` (ORM/SQLAlchemy hoặc sqlite3 minimal).
- CRUD tối thiểu: tạo conversation, chèn message, truy vấn history theo `conversation_id`.
AC:
- Tạo conversation qua API trả về `id` UUID.
- POST message ghi dữ liệu, GET history trả đúng thứ tự.

### T-03 Endpoints chính
- POST `/conversations` → tạo conversation.
- POST `/conversations/{id}/messages` → lưu tin nhắn user, ACK nhanh.
- GET `/conversations/{id}/history` → trả về danh sách messages.
AC:
- OpenAPI hiển thị đủ 3 endpoint, trả mã lỗi hợp lý (401/404/422).
- Latency ACK P95 < 200ms trong môi trường dev khi không compute embedding sync.

### T-04 Ollama client adapters
- Adapter generate: gọi `/api/generate` (model `gpt-oss`, `stream=false`).
- Adapter embedding: gọi `/api/embeddings` (model `bge-m3`).
AC:
- Gọi thử generate với prompt đơn giản trả về chuỗi non-empty.
- Gọi thử embeddings trả về vector 1024-d (hoặc non-empty list; không hard-code dimension).

### T-05 Retrieval (ChromaDB)
- Khởi tạo PersistentClient với `CHROMA_PATH`.
- Hàm truy vấn: vector search + filter theo metadata cơ bản (nếu có) + cắt top-K=3.
- Re-rank đơn giản: ưu tiên same-conversation (nếu có metadata).
AC:
- Truy vấn với câu hỏi khớp nội dung đã index trả về ít nhất 1 mảnh phù hợp.
- Có thể thay đổi K qua config.

### T-06 LangGraph Flow (basic)
- Nodes: classify (retrieve or not), retrieve, respond.
- State: `conversation_id`, `user_id`, `chat_history`, `metadata`.
- Luồng: nhận message → (optional) retrieve → build prompt → generate → lưu response.
AC:
- Happy path chạy end-to-end, response được lưu như message role=assistant.
- Nếu retrieve off, vẫn có response; nếu on, prompt có chèn context.

### T-07 UI Gradio tối thiểu
- Trang chat đơn giản: nhập text, gửi REST API, hiển thị history.
- Config `API_BASE`, `X-API-Key` từ input hoặc env.
AC:
- Có thể gửi và nhận phản hồi một cách ổn định qua UI.
- UI không block khi backend bận (đã ACK sớm).

### T-08 Index knowledge (wiring)
- Xác nhận `scripts/index_knowledge.py` chạy với dataset mẫu `knowledge/`.
- Document hóa quy trình index và collection mặc định dev.
AC:
- Chạy index in ra thống kê, data xuất hiện trong `database/chroma_db/`.
- Retrieval dùng được dữ liệu index trong M5 smoke test.

### T-09 Security cơ bản
- Header `X-API-Key` bắt buộc (trừ health/version), list token từ env (ví dụ `X_API_KEY_ADMIN` + `X_API_KEYS` dạng CSV).
- CORS hạn chế (dev: cho localhost). Log không in PII.
AC:
- Gọi API không token → 401; token sai → 401; token đúng → 200.
- CORS dev cho UI hoạt động khi chạy khác port.

### T-10 Testing (unit + smoke integration)
- Unit: adapter Ollama (mock), chunking/retrieval logic, idempotent upsert (mock Chroma).
- Smoke: gửi message → sinh response → kiểm tra history có assistant message; truy vấn có context nếu KB khớp.
AC:
- `pytest -q` pass các test unit chính.
- Smoke test end-to-end pass trong môi trường dev.

### T-11 Docs & DX
- Cập nhật README: Quick Start (đã thêm checker), thêm How-to chạy backend/UI, scripts.
- Thêm Troubleshooting ngắn (Ollama/Chroma/SQLite thường gặp).
AC:
- Developer mới có thể chạy end-to-end theo README mà không cần hỏi thêm.

### T-12 Ops tối thiểu
- Thêm liveness/readiness routes; hướng dẫn backup Chroma + DB.
- Nêu lệnh check Ollama, index, snapshot.
AC:
- `docs/ops.md` có đủ lệnh cơ bản; runbook ngắn đã cập nhật.

---

## Phụ thuộc (Dependencies)
- T-01 trước T-03/T-06
- T-02 trước T-03/T-06
- T-04 trước T-05/T-06
- T-05 trước T-06/T-10
- T-06 trước T-07/T-10
- T-08 trước T-05 smoke test retrieval

---

## Điều kiện nghiệm thu (Acceptance) theo mốc

### M1 (T-01)
- `uv run uvicorn agent.main:app ...` chạy, `/healthz` 200, auth header enforced.

### M2 (T-02, T-03)
- Tạo conversation và lưu message qua API, GET history trả đúng; P95 ACK < 200ms.

### M3 (T-04, T-05, T-06)
- Gọi Ollama generate/embeddings ok; truy vấn Chroma trả kết quả; flow LangGraph trả response và lưu.

### M4 (T-07, T-08)
- UI gửi/nhận message; index knowledge xong; retrieval sử dụng được dữ liệu index.

### M5 (T-09, T-10, T-11, T-12)
- Tests unit + smoke pass; README/Docs cập nhật; checklists bảo mật cơ bản; ops lệnh sẵn sàng.

---

## Definition of Done (DoD)
- Code build/lint ok; `uv run` có thể khởi chạy backend.
- Quality gates:
  - Build: PASS (không lỗi cú pháp, import)
  - Lint/Typecheck: N/A hoặc PASS nếu cấu hình
  - Tests: Unit + smoke PASS
  - Smoke manual: gửi 1 message, nhận 1 response, history hiển thị đúng
- Tài liệu: README, run_local, ops, plan-phase1.md (tài liệu này)

---

## Kiểm thử & Quy trình xác minh
- Unit (mock external): adapters Ollama, retrieval selection.
- Integration (dev): SQLite + Chroma local + Ollama local.
- Smoke script: gửi 1 message qua API; kiểm tra response và history.
- Optional: k6 tải nhẹ (10–20 VU) để xem ACK P95 ~< 200ms.

---

## Rủi ro & Giảm thiểu
- Ollama model chưa pull → thêm pre-flight (`scripts/check_ollama.py`) và hướng dẫn pull.
- Chroma I/O chậm do đĩa → khuyến nghị SSD local và batch upsert.
- Thiếu Redis → bỏ qua tính năng phụ thuộc Redis ở Phase 1; ghi chú prod cần bật.
- Token rò rỉ → dùng env local, không commit secrets.

---

## Lưu ý triển khai
- Ưu tiên async và không block trong path API; công việc nặng (embedding/upsert) có thể để async nhẹ (dev) hoặc hàng đợi (phase 2).
- Khởi tạo client Ollama/Chroma 1 lần theo process.
- Idempotent keys cho vector: `{message_id}#chunk_{i}`.

---

## Lịch trình gợi ý (tham khảo)
- Ngày 1–2: T-01, T-02, T-03
- Ngày 3–4: T-04, T-05
- Ngày 5–6: T-06, T-07
- Ngày 7: T-08, T-09
- Ngày 8–9: T-10, T-11, T-12

---

## Bước tiếp theo (Next)
1) Khởi tạo `agent/main.py` (T-01) và cấu hình ENV.
2) Tạo data layer SQLite (T-02) và endpoints (T-03).
3) Viết adapters Ollama + Chroma retrieval (T-04/T-05) và ghép LangGraph flow (T-06).
4) UI Gradio tối thiểu (T-07) và xác nhận index (T-08).
5) Hoàn thiện test/docs/ops (T-09…T-12).
