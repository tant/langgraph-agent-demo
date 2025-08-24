# Kiểm thử & Đảm bảo chất lượng (gọn, hành động)

## Mục tiêu
Ngắn, có thể thực thi: đảm bảo correctness (unit), integration (message→worker→vector), performance (load), và resilience (chaos).

## Unit tests
- **Logic nghiệp vụ**: Test các node trong LangGraph (chào hỏi, phân loại, chia tay), logic của Agent-Tool, các hàm xử lý công cụ (tra cứu DB, RAG).
- **Thành phần cốt lõi**: Test session management, chunking, ranking của retriever, idempotent upsert.
- **Chạy nhanh, cô lập**: Dùng `pytest`, mock các phụ thuộc bên ngoài (Ollama, Chroma client).

## Integration tests
- **Luồng End-to-End**: Gửi tin nhắn -> LangGraph chạy đúng luồng -> Agent gọi đúng tool -> Dữ liệu được trả về chính xác.
- **Streaming UI**: Viết script (ví dụ: `scripts/test_ollama_stream.py`) để kết nối tới endpoint streaming và xác nhận nhận được các chunk dữ liệu đúng định dạng.
- **Cơ sở dữ liệu**: Kiểm tra việc ghi và đọc từ các bảng `conversations`, `messages`, và `feedback_logs`.
- **Môi trường CI**: Sử dụng SQLite + ChromaDB trong bộ nhớ hoặc testcontainers cho Chroma/Ollama để đảm bảo môi trường kiểm thử nhất quán.

## Mocks / Fixtures
- Cung cấp fixtures để mock các phản hồi từ Ollama cho việc sinh văn bản và embeddings để tăng tốc độ trong unit tests và CI.
- Chạy một container Ollama thật trong integration tests để có độ tin cậy cao hơn.

## Kiểm thử Hợp đồng / Bảo mật
- **API contract tests**: Xác thực các phản hồi của OpenAPI, hành vi xác thực, và mã lỗi.
- **Security tests**: Kiểm tra prompt-injection, quét các lỗ hổng phụ thuộc (SCA) trong CI.

## Kịch bản kiểm thử cho Tính năng Phase 2

### a. Kiểm thử Streaming UI
- **Mục tiêu**: Đảm bảo frontend nhận và hiển thị tin nhắn từ backend một cách mượt mà.
- **Kịch bản**:
    1.  Chạy script client kết nối tới endpoint `/chat/stream`.
    2.  Gửi một tin nhắn.
    3.  Xác nhận rằng client nhận được các chunk dữ liệu liên tục thay vì chờ toàn bộ phản hồi.
    4.  Kiểm tra xử lý lỗi khi kết nối bị ngắt giữa chừng.

### b. Kiểm thử Vòng lặp Phản hồi
- **Mục tiêu**: Đảm bảo phản hồi của người dùng được ghi nhận chính xác.
- **Kịch bản**:
    1.  Gửi một tin nhắn để nhận câu trả lời từ bot.
    2.  Mô phỏng việc bấm nút 👍 hoặc 👎 qua một request API (nếu có endpoint) hoặc kiểm tra trực tiếp DB.
    3.  Truy vấn bảng `feedback_logs` để xác nhận một bản ghi mới đã được tạo với đúng `message_id` và `feedback_type`.

### c. Kiểm thử Luồng hội thoại đa ngôn ngữ
- **Mục tiêu**: Đảm bảo bot có thể nhận diện và chuyển đổi ngôn ngữ.
- **Kịch bản**:
    1.  Bắt đầu hội thoại bằng tiếng Việt, xác nhận bot trả lời bằng tiếng Việt.
    2.  Gửi tin nhắn yêu cầu chuyển sang tiếng Anh (ví dụ: "speak English please").
    3.  Xác nhận các câu trả lời tiếp theo của bot đều bằng tiếng Anh.

## Example commands
```bash
# unit
pytest -q --maxfail=1 tests/

# integration (ví dụ dùng pytest markers)
pytest -q -m integration

# Chạy kiểm thử streaming
uv run scripts/test_ollama_stream.py
```