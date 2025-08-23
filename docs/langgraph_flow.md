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

## Mô tả node (chi tiết ngắn)

- Node 0 — Greeting (ngoài băng)
	- Mục đích: Thiết lập tông giọng/nhân xưng theo persona ngay khi tạo conversation.
	- Input: conversation_id, persona (`PERSONA_PATH`). Output: 1 message assistant loại “greeting”.
	- Tác dụng phụ: lưu DB; upsert embedding (id = message_id).

- Node 1 — Nhận tin nhắn
	- Input: HTTP request (X-API-Key), conversation_id, user message.
	- Xử lý: đảm bảo conversation; lưu message; enqueue embedding (async, tuỳ chọn sync). Errors: 401, lỗi DB.

- Node 2 — Phân loại intent
	- Input: latest user message, history, persona, `INTENT_CONFIDENCE_THRESHOLD`.
	- Xử lý: LLM trả JSON (intent/confidence/clarify/need_retrieval); fallback từ khóa song ngữ; tạo 1 câu clarify chuẩn hoá (VI/EN) khi cần.
	- Output: intent, intent_confidence, clarify_needed, clarify_questions, need_retrieval_hint, preferred_language.
	- Early exits: (1) clarify_needed → `clarify_stream`; (2) intent=warranty + serial (hoặc đang chờ serial) → `warranty_stream`.

- Clarify (early) — `clarify_stream`
	- Mục đích: Hỏi 1 câu làm rõ rồi END lượt.
	- Input: clarify_questions[0], preferred_language, persona. Output: assistant message loại “clarify”.
	- Tác dụng phụ: lưu DB; upsert embedding.

- Warranty (early) — `warranty_stream`
	- Mục đích: Xử lý nhanh bảo hành theo serial; không đi qua retrieve/LLM nội dung khác.
	- Input: latest user message, trạng thái “đang chờ serial”.
	- Xử lý: trích xuất serial (regex 3–32 [A-Za-z0-9-], có ít nhất 1 chữ số); nếu hợp lệ → tra DB `warranty_records` (DB-only); format ngày D/M/YYYY; thêm follow-up ngắn từ persona.
	- Output: kết quả bảo hành hoặc hướng dẫn nhập serial/hotline. Side-effects: lưu DB; upsert embedding; END lượt.

- Node 3 — Retrieve
	- Input: query (từ user), conversation_id, embed model `bge-m3`.
	- Xử lý: truy vấn ChromaDB (`./database/chroma_db/`), lọc theo metadata; re-rank nếu bật.
	- Output: retrieved_context (chunks).

- Node 4 — Respond (stream)
	- Input: persona (cắt theo `PERSONA_MAX_CHARS`), preferred_language, history, retrieved_context, intent.
	- Xử lý: build prompt gọn; gọi LLM `gpt-oss`; stream chunks (SSE). Output: assistant message (final) lưu sau khi stream.
	- Side-effects: lưu DB; enqueue embedding.

- Node 5 — Hỏi tiếp/Clarify chung
	- Mục đích: Gợi mở nhẹ (FollowUp trong persona), giúp chuyển lượt tiếp theo.
	- Output: 1 câu follow-up ngắn (tuỳ chọn) rồi END lượt.

- Node 6 — END
	- Kết thúc lượt; dọn tài nguyên tạm (nếu có).

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
- Trích xuất serial: regex yêu cầu 3–32 ký tự [A-Za-z0-9-], có ít nhất 1 chữ số, không có khoảng trắng nội bộ.
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
- OLLAMA_HOST/PORT, CHROMA_PATH, CHROMA_COLLECTION, DATABASE_URL, X_API_KEYS
- PERSONA_PATH, PERSONA_MAX_CHARS
- INTENT_CONFIDENCE_THRESHOLD

## Phần mềm hoá (ngắn)
- Persona ngoài code (`prompts/system_persona_vi.md`): lấy Greeting/FollowUp; giới hạn bởi `PERSONA_MAX_CHARS` khi dựng prompt.
- Clarify loop: không đặt trần; câu hỏi chuẩn hoá để đếm attempts ổn định.

## Ghi chú triển khai & lý do (4–8)

4) Streaming: endpoint vs. thuần graph
- Thực tế: endpoint tự điều phối classify → (clarify|warranty) early exits → retrieve → respond_stream để đẩy chunk SSE ngay.
- Lý do: kiểm soát streaming mịn và đơn giản hoá I/O SSE. Có thể chuyển sang conditional edges trong graph nếu cần thuần nhất, nhưng hiện tại không bắt buộc.

5) Khung SSE mở đầu
- Thực tế: emit `data: {"debug":"stream-open"}` ngay đầu stream.
- Lý do: giúp client sớm nhận biết kết nối mở, cải thiện UX và đo latency đầu tiên. Không ảnh hưởng nội dung.

6) Prompt ghi chú intent
- Thực tế: prompt có dòng "Detected intent: <intent>" (nếu đã xác định).
- Lý do: giúp model giữ ngữ cảnh mục tiêu (tư vấn lắp ráp/mua hàng/bảo hành) → trả lời tập trung. Nếu muốn trung lập, có thể bỏ.

7) Tên collection Chroma
- Thực tế: dùng biến môi trường `CHROMA_COLLECTION` (mặc định: `conversations_dev`).
- Lý do: linh hoạt dev/prod; script index vẫn có thể override bằng tham số `--collection`.

8) FollowUp từ persona
- Thực tế: follow-up đã áp dụng ở nhánh bảo hành; đồng thời bổ sung append follow-up ngắn sau trả lời thường (respond_stream) để giữ nhịp hội thoại.
- Lý do: tăng tỉ lệ tiếp tục hội thoại; thống nhất tông giọng từ persona.

Khác biệt nhỏ so với mô tả cũ
- “Đang chờ serial” hiện nhận diện qua metadata trên message assistant (`type = warranty_prompt`|`warranty_prompt_invalid`) khi có, hoặc fallback kiểm tra câu chữ. Lý do: bền vững hơn so với so khớp chuỗi thuần.
