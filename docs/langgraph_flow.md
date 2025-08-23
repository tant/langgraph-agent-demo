# Luồng LangGraph & Thiết kế Agent (gọn, đủ ý)

Tài liệu mô tả flow LangGraph, các node chính và các quyết định triển khai (ChromaDB local, bge-m3 1024-d, backend tách Gradio).

## Luồng tổng thể (rút gọn)
0. START -> 1. Nhận câu hỏi -> 2. Xác định mong đợi (intent)
- Nếu cần làm rõ (clarify) -> hỏi lại (tối đa 3 lần) -> nếu vẫn chưa rõ thì chào lịch sự và END
- Nếu đã rõ intent:
	- Nếu cần retrieve -> 3. Retrieve (ChromaDB) -> 4. Trả lời (LLM) -> 5. Hỏi user có muốn tiếp?
	- Nếu không cần retrieve -> 4. Trả lời -> 5. Hỏi user có muốn tiếp?
- Nếu dừng -> 6. END

## Nodes (tóm tắt hành động)
- Node 1 (Nhận câu hỏi): xác thực token (`X-API-Key`), tạo/đảm bảo conversation, lưu message raw vào DB (message_id).
- Node 2 (Xác định mong đợi/Intent): dùng LLM xác định ý định người dùng và nhu cầu làm rõ; nếu cần clarify thì hỏi lại (tối đa 3 lần) trước khi chuyển bước.
- Node 3 (Retrieve): truy Chroma (filter theo conversation/user), trả về top-K, re-rank theo freshness/same-conversation.
- Node 4 (Trả lời): build prompt (history + retrieved + intent), gọi LLM (`gpt-oss`) để sinh response, lưu response.
- Node 5 (Hỏi tiếp): xác định ý định user -> quay lại Node 1 hoặc END.
- Node 6 (END): mark conversation inactive, schedule retention/cleanup.

## AgentState (rút gọn)
- conversation_id
- user_id
- chat_history (list of {id, role, content, created_at})
- last_updated
- metadata (dict)
	- intent: Optional[str] — assemble_pc | shopping | warranty | unknown
	- intent_confidence: Optional[float]
	- need_retrieval_hint: Optional[bool]
	- clarify_questions: Optional[List[str]]
	- clarify_attempts: Optional[int] — số lần đã hỏi lại trong vòng clarify

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

### Node 2 — Xác định mong đợi (Intent)

Mục tiêu
- Dựa vào câu hỏi hiện tại (ưu tiên cao nhất) và một vài câu gần nhất của user để xác định 1 trong 3 ý định:
	1) Tư vấn lắp ráp máy
	2) Hỏi thông tin về hàng hóa, mua hàng, đặt hàng
	3) Hỏi thông tin về bảo hành, kiểm tra bảo hành, chính sách bảo hành
- Nếu không thuộc 3 ý định trên, sinh ra 1–2 câu hỏi làm rõ (khéo léo, ngắn gọn) để xác định đúng ý định.

Contract (I/O)
- Input:
	- latest_user_message
	- recent_user_messages (2–3 message gần nhất của user nếu có)
	- metadata: conversation_id, user_id
- Output (ghi vào state.metadata):
	- intent: assemble_pc | shopping | warranty | unknown
	- intent_confidence: 0..1
	- need_retrieval_hint: bool (gợi ý cho bước Retrieve)
	- clarify_questions: Optional[List[str]] (1–2 câu)
	- clarify_attempts: int (mặc định 0 nếu chưa có)
	- rationale: string ngắn (phục vụ debug log)

Heuristic gợi ý need_retrieval_hint
- shopping: thường True (cần tồn kho/giá/thuộc tính)
- warranty: True khi cần kiểm tra trạng thái BH/điều kiện; False nếu chỉ hỏi khái niệm chung
- assemble_pc: True khi cần thông số/compat/giá hiện hành; False nếu tư vấn nguyên tắc tổng quan

Logging (debug)
- Log 1 dòng JSON: {intent, confidence, need_retrieval, clarify_needed, first_clarify_question?, conversation_id, user_id}

Từ khóa (song ngữ Việt–Anh)
- assemble_pc (tư vấn lắp ráp máy):
	- vi: "lắp ráp", "ráp máy", "cấu hình", "tư vấn linh kiện", "tương thích", "bottleneck", "ngân sách", "tản nhiệt", "công suất PSU", "BIOS", "driver", "hiệu năng", "FPS", "chơi game", "render"
	- en: "build pc", "pc build", "spec", "compatibility", "bottleneck", "budget", "cooler", "PSU", "motherboard", "CPU", "GPU", "SSD", "HDD", "case", "mini-itx", "micro-atx", "atx", "overclock", "OC", "BIOS", "firmware", "driver", "fps", "gaming", "render", "photoshop", "premiere"
- shopping (mua/đặt hàng):
	- vi: "mua", "đặt", "giá", "bao nhiêu", "khuyến mãi", "giảm giá", "còn hàng", "hết hàng", "giao hàng", "vận chuyển", "thanh toán", "đổi trả", "màu", "phiên bản", "mẫu", "bảo lưu đơn"
	- en: "buy", "order", "price", "cost", "discount", "promotion", "in stock", "out of stock", "shipping", "delivery", "payment", "return", "refund", "color", "model", "SKU"
- warranty (bảo hành/chính sách):
	- vi: "bảo hành", "kiểm tra bảo hành", "chính sách bảo hành", "thời hạn", "serial", "hóa đơn", "lỗi", "1 đổi 1", "DOA", "trung tâm bảo hành", "quy trình"
	- en: "warranty", "check warranty", "warranty policy", "duration", "serial", "SN", "invoice", "defect", "RMA", "service center", "process"

Lưu ý ngôn ngữ
- Mặc định phản hồi và câu hỏi làm rõ bằng tiếng Việt, trừ khi người dùng yêu cầu/viết chủ yếu bằng tiếng Anh.
- Khi xây dựng prompt ở bước trả lời, thêm chỉ dẫn: "Hãy trả lời bằng tiếng Việt, ngắn gọn, lịch sự" (trừ trường hợp người dùng muốn tiếng Anh).

### Vòng Clarify (không giới hạn cố định)

- Nếu `intent == unknown` hoặc `confidence` thấp → sinh `clarify_questions` (1–2 câu ngắn).
- Trả lời ngay cho user bằng câu hỏi làm rõ đầu tiên (không chạy retrieve/LLM trả lời nội dung chính ở lượt này).
- Ghi nhận số lần hỏi lại: `clarify_attempts += 1` (để quan sát/analytics).
- Khi user trả lời, quay lại Node 2 để xác định lại.
- Không đặt trần số lần hỏi lại; luôn kiên nhẫn và khéo léo đưa hội thoại quay về ba nhu cầu chính (assemble_pc / shopping / warranty) để chốt intent.

Gợi ý triển khai
- Thêm các trường nêu trên vào AgentState (metadata) và truyền qua luồng.
- Đếm `clarify_attempts` dựa trên số lượt assistant đã hỏi lại trong history (có thể đánh dấu bằng mẫu câu cố định hoặc metadata nội bộ).
- Trong endpoint stream: nếu `clarify_questions` có giá trị và `clarify_attempts < 3` → stream ngay câu hỏi làm rõ, lưu message assistant (loại “clarify”), sau đó kết thúc lượt.
- Nếu `clarify_attempts >= 3` và vẫn unknown → stream thông điệp kết thúc lịch sự và END.

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
