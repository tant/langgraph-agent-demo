# Chạy cục bộ (Developer Quickstart)

uv là trình quản lý Python/venv nhanh và có thể chạy script kèm phụ thuộc theo yêu cầu. Dưới đây là cách chạy dự án bằng uv theo hướng dẫn chính thức.

1) Cài đặt uv và Python (một lần):

```bash
# Cài uv (xem thêm: https://docs.astral.sh/uv/getting-started/installation/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# (Tùy chọn) Cài Python do uv quản lý
uv python install 3.12
```

2) Chuẩn bị môi trường:

```bash
# Tạo venv nếu bạn muốn venv cục bộ (tùy chọn)
uv venv

# Tạo file biến môi trường (nếu cần)
cp -n .env.local.example .env.local 2>/dev/null || true
```

3) Đảm bảo Ollama đang chạy và model đã được kéo về:

```bash
# Cách 1: dùng tiện ích sẵn có (khuyến nghị)
uv run scripts/check_ollama.py --probe

# Cách 2: thủ công
ollama ls
# Kiểm tra các model cần: gpt-oss (gen), bge-m3 (embeddings)
```

Mẹo: nếu thiếu model, chạy `ollama pull gpt-oss` và/hoặc `ollama pull bge-m3`.

4) Chạy backend (FastAPI) bằng uv + uvicorn:

```bash
uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

5) Chạy script index kiến thức bằng uv run (đã có metadata PEP 723 trong file):

```bash
uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev
```

Tùy chọn:

- Xóa và tạo lại collection trước khi index:
```bash
uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev --clear
```

Biến môi trường ảnh hưởng:

- `CHROMA_PATH` (mặc định `./database/chroma_db/`) — đường dẫn lưu trữ Chroma
- `OLLAMA_EMBEDDING_URL` (mặc định `http://localhost:11434/api/embeddings`)
- `EMBEDDING_MODEL` (mặc định `bge-m3`)
- `CHUNK_SIZE` (mặc định `400`, chia theo số từ — chunking đơn giản)

Thêm (mới): Ollama endpoint configuration

- `OLLAMA_BASE_URL` (ví dụ `http://localhost:11434` or `http://sstc-llm:11434`) — base URL cho Ollama. Nếu đặt, các endpoint phía dưới mặc định sẽ được build từ giá trị này.
- `OLLAMA_GENERATE_URL` — URL đầy đủ cho endpoint generate (ví dụ `${OLLAMA_BASE_URL}/api/generate`).
- `OLLAMA_EMBEDDING_URL` — URL đầy đủ cho endpoint embeddings (ví dụ `${OLLAMA_BASE_URL}/api/embeddings`).
- `OLLAMA_TAGS_URL` — URL đầy đủ cho endpoint tags (ví dụ `${OLLAMA_BASE_URL}/api/tags`).
- `DEFAULT_GENERATE_MODEL` — model mặc định cho generate (mặc định `gpt-oss`).
- `DEFAULT_EMBEDDING_MODEL` — model mặc định cho embeddings (mặc định `bge-m3`).

Ghi chú:
- `scripts/check_ollama.py` và `agent/ollama_client.py` sẽ tự nạp `.env.local` (nếu tồn tại) trước khi xây URL. Điều này cho phép bạn cấu hình host cụ thể (ví dụ `sstc-llm`) trong `.env.local` mà không cần export thủ công trong shell.
- Nếu bạn muốn ghi đè giá trị tạm thời cho một lần chạy, export biến trước khi gọi `uv run`, ví dụ:

```bash
export OLLAMA_BASE_URL="http://sstc-llm:11434"
uv run scripts/check_ollama.py --probe
```

Hoặc export chỉ endpoint embeddings (không cần base):

```bash
export OLLAMA_EMBEDDING_URL="http://sstc-llm:11434/api/embeddings"
uv run scripts/check_ollama.py --probe
```

6) Chạy Gradio UI (tùy chọn) ở terminal khác:

```bash
uv run --with gradio ui/gradio_app.py
```

7) Kiểm thử nhanh: gửi request mẫu tới API và quan sát logs.

Lưu ý quan trọng về uv run:
- Nếu chạy trong thư mục có pyproject.toml nhưng script KHÔNG phụ thuộc vào project, thêm cờ `--no-project` trước tên script.
- Có thể thêm phụ thuộc tạm thời bằng `--with pkg` (ví dụ: `uv run --with rich your.py`).
- Chạy uvicorn qua uv: `uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000`
