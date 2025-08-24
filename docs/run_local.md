# Chạy cục bộ (Developer Quickstart)

`uv` là trình quản lý Python/venv nhanh và có thể chạy script kèm phụ thuộc theo yêu cầu. Dưới đây là cách chạy dự án bằng `uv`.

### 1. Chuẩn bị (làm một lần)

```bash
# Cài uv (xem thêm: https://docs.astral.sh/uv/getting-started/installation/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Tạo venv và cài đặt phụ thuộc
uv venv
uv sync

# Tạo file biến môi trường từ file ví dụ
cp -n .env.local.example .env.local 2>/dev/null || true
```

### 2. Đảm bảo Ollama đang chạy

Đảm bảo dịch vụ Ollama đang hoạt động và các model cần thiết (`gpt-oss`, `bge-m3`, `phi-3`, etc.) đã được tải về.

```bash
# Kiểm tra các model đã có
ollama list

# Nếu thiếu, tải về
ollama pull gpt-oss
ollama pull bge-m3
```

### 3. Index dữ liệu (nếu cần)

Chạy script để nạp và index các tài liệu từ thư mục `knowledge/` vào ChromaDB.

```bash
# Xóa collection cũ và index lại từ đầu
uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev --clear

# Index dữ liệu bảo hành từ file CSV
uv run scripts/upsert_warranty_csv.py --file knowledge/warranty.csv
```

### 4. Chạy Backend (FastAPI)

Mở một terminal và chạy lệnh sau để khởi động server backend.

```bash
uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Chạy Frontend (Gradio UI)

Mở một terminal **khác** và chạy lệnh sau để khởi động giao diện người dùng.

```bash
uv run --with gradio ui/gradio_app.py
```

Sau khi chạy, bạn có thể truy cập giao diện Gradio trong trình duyệt (thường là tại `http://127.0.0.1:7860`).

### 6. Kiểm thử nhanh

Bạn có thể sử dụng các script trong `scripts/` hoặc gửi request API trực tiếp để kiểm tra hoạt động của hệ thống.

```bash
# Gửi một tin nhắn mẫu
sh scripts/send_message.sh "Xin chào"

# Kiểm tra streaming
uv run scripts/test_ollama_stream.py
```