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
ollama ls
# Kiểm tra các model cần: gpt-oss (gen), bge-m3 (embeddings)
```

4) Chạy backend (FastAPI) bằng uv + uvicorn:

```bash
uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
```

5) Chạy script index kiến thức bằng uv run (đã có metadata PEP 723 trong file):

```bash
uv run scripts/index_knowledge.py --source knowledge/ --collection conversations_dev
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
