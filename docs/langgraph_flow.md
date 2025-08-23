# Luồng LangGraph & Thiết kế Agent (gọn, đủ ý)

Tài liệu mô tả flow LangGraph, các node chính và các quyết định triển khai (ChromaDB local, bge-m3 1024-d, backend tách Gradio).

## Luồng tổng thể (rút gọn)
Tiền đề (ngoài vòng lặp):
- 0. Greeting (assistant chủ động chào khi tạo conversation; xảy ra 1 lần, ngoài đường streaming chính)

Vòng lặp cho mỗi tin nhắn của user:
- 1. Nhận câu hỏi (ghi message vào DB, enqueue embedding) →
- 2. Xác định mong đợi (intent)
	- Nhánh sớm (early branch):
		- Nếu cần làm rõ (clarify) → hỏi lại ngay 1 câu ngắn, lịch sự; kết thúc lượt; quay lại 1/2 ở lượt kế tiếp
		- Nếu intent = warranty và đang “chờ serial” hoặc có serial hợp lệ trong tin nhắn → trả kết quả bảo hành ngay; kết thúc lượt; quay lại 1/2 ở lượt kế tiếp
	- Nếu đã rõ intent và không nhánh sớm:
		- Nếu cần retrieve → 3. Retrieve (ChromaDB) → 4. Trả lời (LLM)
		- Nếu không cần retrieve → 4. Trả lời (LLM)
- 5. (tùy) câu gợi mở/clarify chung → kết thúc lượt
- Lặp lại cho đến khi user dừng (END)

## Nodes (tóm tắt hành động)
- Node 0 (Greeting — out-of-band): Khi tạo conversation, assistant tự động gửi lời chào lấy từ persona (file ngoài code), lưu DB và index embedding. Không thuộc vòng xử lý mỗi tin nhắn.
- Node 1 (Nhận câu hỏi): Xác thực `X-API-Key`, đảm bảo conversation, lưu message vào DB (message_id), enqueue embedding.
- Node 2 (Xác định mong đợi/Intent): Phân loại ý định + quyết định clarify; có nhánh sớm cho clarify và warranty-serial. Nếu rơi vào nhánh sớm → stream câu hỏi/hoặc kết quả bảo hành; kết thúc lượt. Nếu không, tiếp tục các bước retrieve/respond.
- Node 3 (Retrieve): Truy Chroma theo conversation/user, top-K + re-rank.
- Node 4 (Trả lời): Build prompt (persona, xưng hô, intent, ngôn ngữ, history, retrieved), gọi LLM `gpt-oss` để sinh response, lưu response.
- Node 5 (Hỏi tiếp/Clarify chung): Giữ nhịp, giúp quay lại vòng 1/2 cho lượt kế.
- Node 6 (END): Đoạn kết, retention/cleanup (nếu áp dụng).

### Vì sao thứ tự 0 → 1 → 2 là hợp lý?
- Node 0 tách riêng khỏi vòng lặp vì chỉ diễn ra khi tạo conversation, giúp thiết lập persona/tông giọng và có lời chào sớm mà không chặn đường xử lý chính.
- Node 1 trước Node 2 vì hệ thống cần lưu tin nhắn user vào DB để:
	- Phân loại intent dựa trên history bền vững (không phụ thuộc RAM tạm thời)
	- Lọc truy vấn Chroma theo conversation/user từ metadata của message
- Node 2 ngay sau Node 1 để có thể rẽ nhánh sớm (clarify/warranty-serial) rồi kết thúc lượt, đảm bảo độ phản hồi nhanh và logic tuyến tính, trước khi tiêu tốn tài nguyên cho retrieve/LLM.

## Đồ thị LangGraph (Nodes & Edges)

Entry point: `classify`

Streaming graph
- Nodes: `classify` → `retrieve` → `respond_stream`
- Edges:
	- `classify` → `retrieve`
	- `retrieve` → `respond_stream`
	- `respond_stream` → `END`

Mapping code → node
- `classify` → `agent.langgraph_flow.classify_node`
- `retrieve` → `agent.langgraph_flow.retrieve_node`
- `respond_stream` → `agent.langgraph_flow.stream_respond_node`

Mở rộng (đề xuất để thuần graph hơn với early exits)
- Bổ sung nodes: `clarify_stream` và `warranty_stream` (đã có sẵn trong code), và dùng conditional edges từ `classify`:
	- Nếu `clarify_needed` → `clarify_stream` → `END`
	- Nếu `intent == 'warranty'` và (có serial hợp lệ hoặc đang chờ serial) → `warranty_stream` → `END`
	- Ngược lại → `retrieve` → `respond_stream` → `END`

Early exits (được xử lý ở API trước khi vào các node tiếp theo)
- Clarify Early Exit: nếu `clarify_needed == true` → stream 1 câu hỏi làm rõ và `return` (kết thúc lượt).
- Warranty Early Exit: nếu thỏa điều kiện bảo hành (intent = `warranty` kèm serial, hoặc lượt trước đang chờ serial và lượt này có serial hợp lệ) → trả kết quả bảo hành và `return`.

Gợi ý mở rộng (nếu muốn thuần “graph” hơn)
- Có thể bổ sung các node phụ và `add_conditional_edges`:
	- `classify` → (`clarify` | `warranty_direct` | `retrieve`) dựa trên điều kiện state.
	- `clarify` → `END` (kết thúc lượt); lượt sau quay lại `classify` do endpoint khởi tạo lại state.
	- `warranty_direct` → `END` (kết thúc lượt); tương tự clarify.

## AgentState (rút gọn)
- conversation_id
- user_id
- chat_history (list of {id, role, content, created_at})
- last_updated
- intent: Optional[str] — assemble_pc | shopping | warranty | unknown
- intent_confidence: Optional[float]
- need_retrieval_hint: Optional[bool]
- clarify_questions: Optional[List[str]]
- clarify_attempts: Optional[int] — số lần đã hỏi lại trong vòng clarify (chỉ để quan sát/analytics, không để cắt hội thoại)
- preferred_language: Optional[str] — 'vi' (mặc định) hoặc 'en' nếu phát hiện tiếng Anh chiếm ưu thế

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
- Phát hiện ngôn ngữ dựa trên tin nhắn đầu tiên của user; khi không chắc, mặc định 'vi'.
- Quy tắc xưng hô cố định: AI xưng "em", gọi người dùng là "quý khách".
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
- Trong endpoint stream: nếu `clarify_questions` có giá trị → stream ngay câu hỏi làm rõ (câu đầu tiên), lưu message assistant (loại “clarify”), sau đó kết thúc lượt; chờ user phản hồi rồi quay lại Node 2.
- Không áp dụng ngưỡng dừng cứng theo số lần; luôn kiên nhẫn và khéo léo dẫn dắt về 3 nhóm nhu cầu chính.

### Persona bên ngoài code

- Persona được lưu trong file ngoài code, ví dụ: `prompts/system_persona_vi.md` và nạp qua biến môi trường `PERSONA_PATH`.
- Lời chào đầu cuộc hội thoại (Node 0) lấy từ dòng có tiền tố "Greeting:" trong persona.
- Nội dung persona được đính kèm vào prompt trả lời và bị giới hạn kích thước bởi `PERSONA_MAX_CHARS` để an toàn.

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

### Bổ sung (env mới liên quan đến persona/intent)
- PERSONA_PATH (default: ./prompts/system_persona_vi.md)
- PERSONA_MAX_CHARS (default: 4000)
- INTENT_CONFIDENCE_THRESHOLD (default: 0.5)

## Nhánh chuyên biệt: Warranty (bảo hành)

- Kích hoạt khi: (a) intent = `warranty` và không cần làm rõ, hoặc (b) ở lượt trước trợ lý vừa yêu cầu số serial/nhắc quy tắc nhập serial và lượt này người dùng gửi serial.
- Nếu chưa có serial trong câu người dùng gần nhất:
	- Hỏi: "Quý khách vui lòng cung cấp số serial của sản phẩm để em kiểm tra thời hạn bảo hành ạ?" (giữ nguyên định dạng SSE/data: {"chunk": ...}).
- Nếu đã yêu cầu serial ở lượt trước nhưng vẫn không trích xuất được serial hợp lệ:
	- Nhắc rõ quy tắc: "Em chưa nhận diện được số serial hợp lệ. Quý khách vui lòng nhập số serial (3–32 ký tự, gồm chữ cái, chữ số hoặc dấu gạch nối), ví dụ: ABC123-XYZ."
- Quy tắc nhận diện serial: chuỗi 3–32 ký tự gồm [A–Z, a–z, 0–9, '-'] (không khoảng trắng nội bộ).
- Khi có serial hợp lệ, trả kết quả ngay (không đi qua bước retrieve/LLM trả lời nội dung khác ở lượt này):
	- Nếu tìm thấy: "Thông tin bảo hành: Sản phẩm '<product_name>', Serial '<serial>', hết bảo hành vào ngày <date>. Quý khách có cần em hỗ trợ gì thêm không ạ?"
	- Nếu không tìm thấy: "Số serial này hiện chưa có trên hệ thống. Quý khách vui lòng gọi hotline để được hỗ trợ thêm ạ. Quý khách có cần em hỗ trợ gì thêm không ạ?"
- Kết thúc lượt sau khi trả lời; lượt tiếp theo quay lại vòng xác định intent (classify). Trạng thái "đang chờ serial" chỉ được giữ nếu ngay trước đó trợ lý thật sự yêu cầu/nhắc quy tắc serial; trả lời kết quả bảo hành không giữ trạng thái này.
- Các tin nhắn trợ lý phát sớm (câu hỏi serial/nhắc quy tắc/kết quả bảo hành) đều được lưu vào DB và upsert embedding để đảm bảo ngữ cảnh lượt sau.
- Định dạng message/SSE giữ nguyên như hiện tại.

Ghi chú (dev tạm thời):
- Trong môi trường demo hiện tại, lookup bảo hành đang được hardcode để test nhanh:
	- Serial `0979825281` → trả "S23 Ultra", hết bảo hành ngày `12/8/2026`.
	- Serial khác → coi như không có trên hệ thống → gợi ý gọi hotline.
- Khi kết nối database thật, phần tra cứu sẽ chuyển sang query `warranty_records` như mô tả ban đầu, không thay đổi giao tiếp/SSE.
