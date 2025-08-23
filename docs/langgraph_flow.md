# LangGraph Flow — Tài liệu rút gọn

Mục tiêu: mô tả ngắn gọn cấu trúc LangGraph, cách định tuyến, thuật toán phân loại intent, và nhánh bảo hành.

## Luồng điều khiển (per message)
- 0. Greeting (ngoài băng): khi tạo conversation, assistant tự chào (từ persona), lưu DB + embed.
- 1. Nhận tin nhắn: lưu message vào DB, enqueue embedding.
- 2. Phân loại intent: xác định intent, cần clarify hay không, và gợi ý retrieval.
	- Early exit 1: cần làm rõ → stream 1 câu hỏi ngắn → END lượt.
	- Early exit 2: intent=warranty và có/đang chờ serial → kiểm tra bảo hành → END lượt.
- 3. Retrieve (nếu cần) → 4. Respond (stream) → END lượt.

## Nodes & mapping
- classify → `agent.langgraph_flow.classify_node`
- retrieve → `agent.langgraph_flow.retrieve_node`
- respond_stream → `agent.langgraph_flow.stream_respond_node`
- clarify_stream (early) → `agent.langgraph_flow.clarify_stream_node`
- warranty_stream (early) → `agent.langgraph_flow.warranty_stream_node`

Graph (streaming): classify → retrieve → respond_stream → END
Điều kiện rẽ nhánh được xử lý sớm ở endpoint (hoặc có thể thêm conditional edges trong graph nếu muốn thuần graph).

## Thuật toán phân loại intent (ngắn gọn)
- Nhận diện ngôn ngữ từ tin nhắn user đầu tiên (VI mặc định nếu không chắc).
- Gọi LLM để trả JSON: `intent | confidence | need_retrieval | clarify_needed | clarify_questions`.
- Dự phòng từ khóa song ngữ nếu kết quả yếu (`unknown` hoặc `confidence` < ngưỡng).
- Nếu chưa rõ → đặt `clarify_needed` và cung cấp 1 câu hỏi chuẩn hoá (VI/EN); clarify không giới hạn vòng.
- Gợi ý retrieval: mặc định True cho assemble_pc/shopping/warranty.

Ngưỡng: `INTENT_CONFIDENCE_THRESHOLD` (env, mặc định 0.5).

## AgentState (tối thiểu cần dùng)
- conversation_id, user_id
- chat_history: [{role, content}, ...]
- intent, intent_confidence
- need_retrieval_hint, clarify_questions, clarify_attempts
- preferred_language
- retrieved_context, response

Ghi chú: vector id = `messages.id` khi upsert vào Chroma.

## Lưu trữ & Retrieval
- Messages lưu DB; vectors trong ChromaDB `./database/chroma_db/`.
- Mapping: `messages.id` → vector id; model embed: `bge-m3` (1024-d) qua Ollama.
- Upsert idempotent; xóa vector khi xoá message/conversation.

## Warranty (bảo hành)
- Kích hoạt: intent=warranty và không cần clarify, hoặc lượt trước đang chờ serial và lượt này gửi serial hợp lệ.
- Trích xuất serial: regex yêu cầu 3–32 ký tự [A-Za-z0-9-], có ít nhất 1 chữ số.
- Nếu thiếu/không hợp lệ: nhắc lại quy tắc nhập hoặc hỏi xin serial (VI/EN theo persona).
- Khi có serial hợp lệ: tra DB `warranty_records` (DB-only), trả kết quả; thêm câu follow-up mềm (đọc từ persona nếu có). Kết thúc lượt.

Nạp dữ liệu bảo hành (CSV → DB):
- File: `knowledge/warranty.csv` (headers: `serial,product_name,warranty_end_date`; date: `YYYY-MM-DD` hoặc `DD/MM/YYYY`).
- Script: `scripts/upsert_warranty_csv.py` (commit mặc định). Ví dụ chạy với uv:
	- `uv run python - <<'PY'` + gọi `scripts.upsert_warranty_csv.main('knowledge/warranty.csv', False)`.

## API (rút gọn)
- POST /conversations → tạo conversation, auto greeting (201)
- POST /conversations/{id}/messages → lưu message (202), assistant flow chạy nền
- POST /conversations/{id}/stream → stream câu trả lời (SSE)
- GET  /conversations/{id}/history → trả lịch sử

## Cấu hình (env chính)
- OLLAMA_HOST/PORT, CHROMA_PATH, DATABASE_URL, X_API_KEYS
- PERSONA_PATH, PERSONA_MAX_CHARS
- INTENT_CONFIDENCE_THRESHOLD

## Phần mềm hoá (ngắn)
- Persona ngoài code (`prompts/system_persona_vi.md`): lấy Greeting/FollowUp; giới hạn bởi `PERSONA_MAX_CHARS` khi dựng prompt.
- Clarify loop: không đặt trần; câu hỏi chuẩn hoá để đếm attempts ổn định.
