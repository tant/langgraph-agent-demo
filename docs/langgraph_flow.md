# LangGraph Flow — Tài liệu chi tiết

Mô tả đầy đủ cấu trúc LangGraph, logic phân loại intent 2-nhánh (shopping + ### 5. Clarify Stream Node (Early Exit)
**Kích hoạt**: `clari### 5. Clarify Stream Node (Early Exit)
**Kích hoạt**: `clarify_needed = true`

**LLM-Based Social Intent Detection**:
Bot sử dụng LLM để detect và generate social responses thay vì pattern matching cứng nhắc:

**LLM Processing**:
- Phân tích user message để xác định có social/personal intent không
- Generate phản hồi phù hợp với văn hóa và context
- Giọng nữ, xưng "em", gọi "quý khách"
- Đặt ranh giới hợp lý khi cần thiết

**Ví dụ LLM Social Responses**:
- "em khỏe không" → "Em khỏe, cảm ơn quý khách đã hỏi ạ"
- "đi chơi không" → "Em đang làm việc ạ, không thể đi chơi được"  
- "tên gì" → "Em là trợ lý AI của SSTC ạ"
- "làm gì đây" → "Em đang hỗ trợ khách hàng ạ"
- "có bạn trai không" → "Em là AI nên không có chuyện đó ạ"

**Response Format**: `{LLM Social Response}. {Business Redirect}`

**Standard Clarify** (khi LLM không detect social intent):
- **VI**: "Dạ em rất vui được giúp ạ — quý khách đang cần tư vấn mua hàng, kiểm tra bảo hành hay muốn trò chuyện thôi ạ?"
- **EN**: "Hi! I'm happy to help — are you looking for shopping advice, a warranty check, or just to chat?"

**Ưu điểm LLM approach**:
- ✅ **Flexible**: Hiểu được context và nuance
- ✅ **Natural**: Generate responses tự nhiên, không cứng nhắc
- ✅ **Adaptive**: Có thể handle các social intents mới
- ✅ **Cultural**: Phù hợp với văn hóa và cách xưng hô Việt Nam
- ✅ **Consistent**: Maintain giọng điệu và persona đồng nhất

### 6. Warranty Stream Node (Early Exit)  
**Kích hoạt**: intent=warranty và không cần clarify

**Serial Detection**:
- **Regex**: `(?<![A-Za-z0-9-])(?=[A-Za-z0-9-]*\d[A-Za-z0-9-]*)([A-Za-z0-9-]{3,32})(?![A-Za-z0-9-])`
- **Rules**: 3-32 chars, [A-Za-z0-9-], phải có ít nhất 1 số, không có space

**Flow**:
1. **Không có serial**: "Quý khách vui lòng cung cấp số serial..."
2. **Serial invalid**: "Em chưa nhận diện được số serial hợp lệ..."
3. **Serial hợp lệ**: 
   - Query `warranty_records` table (DB-only)
   - Format: "Thông tin bảo hành: Sản phẩm '{name}', Serial '{serial}', hết bảo hành vào ngày {d/m/y}"
   - Append persona follow-up

**Metadata Tracking**:
- Lưu `warranty_meta: {kind: "prompt|result", found: bool, serial: str}`
- Assistant message metadata: `type = "warranty_prompt|warranty_result"`

### 7. Retrieve Node
**Kích hoạt**: intent=shopping và need_retrieval=true

**Processing**:
- Query ChromaDB với `bge-m3` embeddings (1024-d)
- Filter: conversation_id, user_id
- Collection: `CHROMA_COLLECTION` env (default: `conversations_dev`)
- Re-rank results với `simple_rerank()`

**Output**: `retrieved_context` chunks cho shopping advice

### 8. Stream Respond Node
**Input**: persona (max `PERSONA_MAX_CHARS`), preferred_language, history, retrieved_context, detected intent

**Prompt Building**:
```
System Persona: [persona content]
Retrieved context: [chunks if any]
Detected intent: shopping|warranty  # bias toward focused response
Instruction: [VI/EN based on preferred_language]
Conversation: [chat history]
Assistant:
```

**Streaming**: Chunks qua `generate_text_stream()` → SSE format

### 9. Persona Follow-up (Auto-append)
**Source**: `FollowUp:` line từ persona file
**Timing**: Sau khi stream_respond_node hoàn thành
**Example**: "Em còn có thể hỗ trợ tư vấn mua hàng, kiểm tra bảo hành hoặc trò chuyện cùng quý khách — quý khách muốn em giúp gì thêm không ạ?"d = true`

**Gentle Clarify Questions**:
- **VI**: "Dạ em rất vui được giúp ạ — quý khách đang cần tư vấn mua hàng, kiểm tra bảo hành hay muốn trò chuyện thôi ạ?"
- **EN**: "Hi! I'm happy to help — are you looking for shopping advice, a warranty check, or just to chat?"

**Đặc điểm**:
- Mở rộng hơn 2 intent (cho phép "just to chat")
- Giọng nữ, nhẹ nhàng, không ép buộc
- Cho phép social interaction tự nhiên
- **END** turn sau khi hỏi

### 6. Warranty Stream Node (Early Exit)  
**Kích hoạt**: intent=warranty và không cần clarify

**Serial Detection**:
- **Regex**: `(?<![A-Za-z0-9-])(?=[A-Za-z0-9-]*\d[A-Za-z0-9-]*)([A-Za-z0-9-]{3,32})(?![A-Za-z0-9-])`
- **Rules**: 3-32 chars, [A-Za-z0-9-], phải có ít nhất 1 số, không có space

**Flow**:
1. **Không có serial**: "Quý khách vui lòng cung cấp số serial..."
2. **Serial invalid**: "Em chưa nhận diện được số serial hợp lệ..."
3. **Serial hợp lệ**: 
   - Query `warranty_records` table (DB-only)
   - Format: "Thông tin bảo hành: Sản phẩm '{name}', Serial '{serial}', hết bảo hành vào ngày {d/m/y}"
   - Append persona follow-up

**Metadata Tracking**:
- Lưu `warranty_meta: {kind: "prompt|result", found: bool, serial: str}`
- Assistant message metadata: `type = "warranty_prompt|warranty_result"`

### 7. Retrieve Node
**Kích hoạt**: intent=shopping và need_retrieval=true

**Processing**:
- Query ChromaDB với `bge-m3` embeddings (1024-d)
- Filter: conversation_id, user_id
- Collection: `CHROMA_COLLECTION` env (default: `conversations_dev`)
- Re-rank results với `simple_rerank()`

**Output**: `retrieved_context` chunks cho shopping advice

### 8. Stream Respond Node
**Input**: persona (max `PERSONA_MAX_CHARS`), preferred_language, history, retrieved_context, detected intent

**Prompt Building**:
```
System Persona: [persona content]
Retrieved context: [chunks if any]
Detected intent: shopping|warranty  # bias toward focused response
Instruction: [VI/EN based on preferred_language]
Conversation: [chat history]
Assistant:
```

**Streaming**: Chunks qua `generate_text_stream()` → SSE format

### 9. Persona Follow-up (Auto-append)
**Source**: `FollowUp:` line từ persona file
**Timing**: Sau khi stream_respond_node hoàn thành
**Example**: "Em còn có thể hỗ trợ tư vấn mua hàng, kiểm tra bảo hành hoặc trò chuyện cùng quý khách — quý khách muốn em giúp gì thêm không ạ?"), xử lý ngôn ngữ, và các tính năng nâng cao.

## Tổng quan hệ thống

### Chính sách Intent (2 nhánh chính)
- **shopping**: Tư vấn mua hàng, gợi ý sản phẩm, so sánh → yêu cầu retrieval từ knowledge base
- **warranty**: Hỗ trợ bảo hành, kiểm tra serial → DB-only lookup, không qua retrieval
- **unknown**: Khi không rõ intent → clarify nhẹ nhàng, giọng nữ, không ép buộc

### Đặc điểm tương tác
- **Greeting thân thiện**: Assistant gửi lời chào dễ thương khi intent rõ ràng
- **Language-switch**: Phát hiện yêu cầu "speak English" → trả lời ngay "sure, you can speak english with me" + chuyển ngôn ngữ
- **Clarify nhẹ nhàng**: Câu hỏi mở, cho phép trò chuyện tự nhiên, không chỉ hỏi 2 intent
- **Social boundaries**: Xử lý yêu cầu xã giao ("hang out") một cách thân thiện nhưng có giới hạn

## Luồng điều khiển (per message)

1. **Greeting** (tự động khi tạo conversation): Assistant tự chào từ persona, lưu DB + embed
2. **Nhận tin nhắn**: Lưu user message, enqueue embedding 
3. **Language detection & switch**: Phát hiện yêu cầu English → ack ngay + chuyển ngôn ngữ
4. **Cute greeting**: Nếu intent rõ (shopping/warranty) → gửi lời chào dễ thương "Dạ em rất vui được giúp quý khách! 💖"
5. **Phân loại intent**: 
   - **Early exit A**: cần clarify → stream câu hỏi mở, nhẹ nhàng → END
   - **Early exit B**: intent=warranty → xử lý bảo hành DB-only → END
6. **Retrieve** (chỉ shopping) → **Respond** (stream) + follow-up → END

## Nodes & Implementation

### Mapping chính
- **classify** → `agent.langgraph_flow.classify_node`
- **retrieve** → `agent.langgraph_flow.retrieve_node` 
- **respond_stream** → `agent.langgraph_flow.stream_respond_node`
- **clarify_stream** → `agent.langgraph_flow.clarify_stream_node` (early exit)
- **warranty_stream** → `agent.langgraph_flow.warranty_stream_node` (early exit)

### Luồng streaming trong endpoint
```
POST /conversations/{id}/stream:
  ├── classify_node() 
  ├── detect_english_request() → emit "sure, you can speak english with me"
  ├── emit_cute_greeting() → "Dạ em rất vui được giúp! 💖" (nếu intent rõ)
  ├── warranty_stream_node() → END (nếu warranty)
  ├── clarify_stream_node() → END (nếu cần clarify)  
  ├── retrieve_node() (nếu shopping)
  ├── stream_respond_node()
  └── append_persona_followup()
```

## Chi tiết từng Node

### 1. Greeting (Auto-generated)
- **Kích hoạt**: Khi tạo conversation mới
- **Input**: `PERSONA_PATH` 
- **Behavior**: Đọc `Greeting:` từ persona file → lưu DB + embed
- **Example**: "Chào quý khách! Em là nhân viên SSTC, rất vui được hỗ trợ quý khách..."

### 2. Language Detection & Switch
- **Kích hoạt**: Phát hiện cụm từ "speak english", "tiếng anh được không", etc.
- **Response**: Emit ngay chunk "sure, you can speak english with me" 
- **Effect**: Set `preferred_language = "en"` cho conversation
- **Persist**: Lưu ack message vào DB để xuất hiện trong history

### 3. Cute Greeting  
- **Kích hoạt**: Intent confident (shopping/warranty) và không cần clarify
- **VI**: "Dạ em rất vui được giúp quý khách! 💖 Em sẽ hỗ trợ ngay ạ."
- **EN**: "Hi! I'm happy to help 💖 I'll assist you right away."
- **Persist**: Lưu greeting vào DB + embed

### 4. Classify Node (Intent Detection)
**Input**: Latest user message, chat history, `INTENT_CONFIDENCE_THRESHOLD`

**LLM Processing**:
```json
{
  "intent": "shopping|warranty|unknown",
  "confidence": 0.0-1.0,
  "need_retrieval": false,
  "clarify_needed": false, 
  "clarify_questions": ["..."],
  "rationale": "..."
}
```

**Keyword Fallback** (bilingual):
- **Shopping**: mua, đặt, giá, khuyến mãi, buy, order, price, discount...
- **Warranty**: bảo hành, serial, warranty, check warranty...

**Logic**:
- Nếu `unknown` hoặc `confidence < threshold` → `clarify_needed = true`
- Shopping → `need_retrieval = true` (cần knowledge base)
- Warranty → `need_retrieval = false` (DB-only lookup)

**Output**: intent, confidence, clarify_needed, preferred_language

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
	- Xử lý: LLM trả JSON (intent/confidence/clarify/need_retrieval); fallback từ khóa song ngữ; tạo 1 câu clarify chuẩn hoá (VI/EN) khi cần. Chỉ còn hai intent hẹp: `shopping` (tư vấn/mua hàng) và `warranty` (bảo hành). Nếu không chắc, trả `unknown` và hỏi một câu làm rõ ngắn, nhẹ nhàng, giọng nữ, không ép.
	- **Output**: intent, confidence, clarify_needed, preferred_language
	- Early exits: (1) clarify_needed → `clarify_stream`; (2) intent=warranty + serial (hoặc đang chờ serial) → `warranty_stream`.

- Clarify (early) — `clarify_stream`
	- Mục đích: Hỏi 1 câu làm rõ rồi END lượt.
	- Input: clarify_questions[0], preferred_language, persona. Output: assistant message loại “clarify”.
	- Tác dụng phụ: lưu DB; upsert embedding.

	Notes:
	- The clarify question is intentionally open-ended and gentle (e.g. EN: "Hi! I'm happy to help — are you looking for shopping advice, a warranty check, or just to chat?"; VI: "Dạ em rất vui được giúp ạ — quý khách đang cần tư vấn mua hàng, kiểm tra bảo hành hay muốn trò chuyện thôi ạ?").
	- When the user explicitly asks to speak English, the stream endpoint will first emit a short English acknowledgement ("sure, you can speak english with me") and set the conversation's preferred language to English for subsequent messages.

- Warranty (early) — `warranty_stream`
	- Mục đích: Xử lý nhanh bảo hành theo serial; không đi qua retrieve/LLM nội dung khác.
	- Input: latest user message, trạng thái “đang chờ serial”.
	- Xử lý: trích xuất serial (regex 3–32 [A-Za-z0-9-], có ít nhất 1 chữ số); nếu hợp lệ → tra DB `warranty_records` (DB-only); format ngày D/M/YYYY; thêm follow-up ngắn từ persona.
	- Output: kết quả bảo hành hoặc hướng dẫn nhập serial/hotline. Side-effects: lưu DB; upsert embedding; END lượt.

		Notes:
		- Warranty lookup is DB-only: the node queries `warranty_records` in the SQL DB and does not call retrieval/LLM for the actual lookup result.
		- After a warranty result (found or not), the node appends a short persona-driven follow-up sentence (if present) to keep the conversation friendly.

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

	Guideline for social/chat requests:
	- If a user makes a social request ("can you hangout with me", "do you want to chat"), the assistant should respond warmly and set boundaries where necessary. Example: acknowledge in the user's language, e.g. EN: "sure, you can speak english with me. I can chat and keep you company here, but I can't meet in person — how can I help?"; VI equivalent should be gentle and non-pushy.

- Node 6 — END
	- Kết thúc lượt; dọn tài nguyên tạm (nếu có).

## Xử lý Social/Chat Requests

### Hướng dẫn tương tác xã giao MỚI (LLM-Based)
**Nguyên tắc chính**: Bot sử dụng LLM để detect và generate social responses tự nhiên, luôn acknowledge user's intent trước khi dẫn dắt về business.

**LLM Social Detection Process**:
1. **Input Analysis**: LLM phân tích user message để xác định social intent
2. **Context Understanding**: Hiểu được nuance, văn hóa, và context
3. **Response Generation**: Tạo phản hồi phù hợp với giọng nữ, xưng hô "em-quý khách"
4. **Boundary Setting**: Đặt ranh giới hợp lý khi cần thiết
5. **Business Redirect**: Dẫn dắt nhẹ nhàng về shopping/warranty topics

**Ví dụ conversation (LLM-powered)**:
```
User: em khỏe không
Bot: Em khỏe, cảm ơn quý khách đã hỏi ạ. Quý khách có cần em hỗ trợ về thông tin hàng hóa hay bảo hành không ạ?

User: đi chơi không em  
Bot: Em đang làm việc ạ, không thể đi chơi được. Quý khách có cần em hỗ trợ về thông tin hàng hóa hay bảo hành không ạ?

User: có bạn trai không
Bot: Em là AI nên không có chuyện đó ạ. Quý khách có cần em hỗ trợ về thông tin hàng hóa hay bảo hành không ạ?
```

### Ưu điểm LLM approach vs Pattern Matching:

**✅ LLM Benefits**:
- **Flexible & Adaptive**: Hiểu được các cách diễn đạt mới, không giới hạn patterns
- **Natural Responses**: Generate phản hồi tự nhiên, phù hợp context
- **Cultural Awareness**: Hiểu văn hóa, cách xưng hô, và social norms Việt Nam
- **Contextual Understanding**: Hiểu được ý nghĩa thực sự, không chỉ keyword matching
- **Consistent Persona**: Maintain giọng điệu và personality đồng nhất

**❌ Pattern Matching Limitations**:
- Cứng nhắc, chỉ detect được patterns đã định trước
- Không hiểu context và nuance
- Khó maintain khi cần thêm patterns mới
- Responses không tự nhiên, có thể repetitive

### Format phản hồi chuẩn (LLM-generated):
`{LLM Social Response}. {Gentle Business Redirect}`

**Business Redirect Options**:
- **VI**: "Quý khách có cần em hỗ trợ về thông tin hàng hóa hay bảo hành không ạ?"
- **EN**: "Can I help you with shopping or warranty questions?"

## Persona & Tone

### Persona File (`prompts/system_persona_vi.md`)
**Cấu trúc**:
```markdown
Chatbot Persona...

Greeting: [initial greeting cho conversation mới]
FollowUp: [append sau responses để maintain conversation flow]
```

**Đặc điểm giọng điệu**:
- **Xưng hô**: Em (AI) - Quý khách (User)  
- **Tone**: Lịch sự, thân thiện, ngắn gọn
- **Female voice**: Nhẹ nhàng, không ép buộc
- **Responsive**: Song ngữ VI/EN based on user preference

### Language Detection & Switch
**Auto-detection**: Dựa trên message đầu tiên của user
- **VI markers**: diacritics, "anh", "em", "không", "dạ", "ạ"
- **EN markers**: "hello", "hi", "please", "how", "what"
- **Default**: VI nếu không chắc

**Switch triggers**: "speak english", "tiếng anh được không", "can we speak english"
**Response**: Immediate ack + language change cho toàn bộ conversation

## Data & Storage

### AgentState Structure
```python
{
  "conversation_id": str,
  "user_id": str, 
  "chat_history": [{"role": "user|assistant", "content": str}],
  "metadata": {"conversation_id": str, "user_id": str},
  "intent": "shopping|warranty|unknown",
  "intent_confidence": float,
  "need_retrieval_hint": bool,
  "clarify_questions": [str],
  "clarify_attempts": int,
  "preferred_language": "vi|en",
  "retrieved_context": [dict],  # từ ChromaDB
  "response": str,              # final response
  "stream": bool
}
```

### Database Schema
**Messages**: id, conversation_id, sender, text, created_at, metadata
**Conversations**: id, user_id, created_at, metadata  
**WarrantyRecords**: serial (PK), product_name, warranty_end_date

### Vector Storage
**ChromaDB**: `./database/chroma_db/`
- Collection: `CHROMA_COLLECTION` env (default: `conversations_dev`)
- Embeddings: `bge-m3` qua Ollama (1024 dimensions)
- Mapping: `messages.id` → vector id
- Metadata: conversation_id, user_id, message_id, created_at

## Warranty Management

### Data Loading (CSV → DB)
**File format** (`knowledge/warranty.csv`):
```csv
serial,product_name,warranty_end_date
ABC123,Laptop Dell,2024-12-31
XYZ789,Mouse Logitech,30/06/2025
```

**Commands**:
```bash
# Validate only
uv run scripts/upsert_warranty_csv.py --file knowledge/warranty.csv --dry-run

# Write to DB  
uv run scripts/upsert_warranty_csv.py --file knowledge/warranty.csv
```

**Date formats**: YYYY-MM-DD hoặc DD/MM/YYYY

### Serial Validation Rules
- **Length**: 3-32 characters
- **Characters**: A-Z, a-z, 0-9, dấu gạch nối (-)
- **Required**: Ít nhất 1 chữ số
- **Forbidden**: Khoảng trắng internal
- **Regex**: `(?<![A-Za-z0-9-])(?=[A-Za-z0-9-]*\d[A-Za-z0-9-]*)([A-Za-z0-9-]{3,32})(?![A-Za-z0-9-])`

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
