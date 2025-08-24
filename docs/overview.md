# Tổng quan dự án

Mục tiêu: xây dựng một ứng dụng chat đa người dùng (multi-user chat) sử dụng LangGraph và Ollama, với các tính năng nâng cao trong Phase 2 để cải thiện trải nghiệm người dùng và khả năng của chatbot.

## Các tính năng chính (Phase 2)

- **Kiến trúc Agent-Tool lai**: Sử dụng LangGraph để điều phối một luồng hội thoại có cấu trúc (chào hỏi, tạm biệt) kết hợp với một vòng lặp Agent-Tool linh hoạt để xử lý các tác vụ phức tạp.
- **Giao diện Streaming**: Giao diện người dùng (Gradio) kết nối với backend (FastAPI) qua cơ chế streaming, giúp hiển thị phản hồi của chatbot ngay lập tức, tạo cảm giác tương tác tự nhiên và mượt mà.
- **Vòng lặp Phản hồi (Feedback Loop)**: Người dùng có thể đánh giá câu trả lời của chatbot (👍/👎). Dữ liệu này được thu thập để phân tích và fine-tuning mô hình trong tương lai, giúp hệ thống liên tục tự cải thiện.
- **Hỗ trợ đa ngôn ngữ**: Tự động nhận diện và phản hồi bằng ngôn ngữ của người dùng (tiếng Việt/tiếng Anh), đồng thời cho phép chuyển đổi ngôn ngữ giữa cuộc trò chuyện.
- **Quản lý tri thức nâng cao**: Phân tách rõ ràng giữa tri thức có cấu trúc (DB cho sản phẩm, bảo hành) và tri thức phi cấu trúc (RAG cho chính sách, FAQ), cho phép Agent truy xuất thông tin hiệu quả.
- **Xử lý hội thoại tự nhiên**: Cải thiện khả năng xử lý các cuộc trò chuyện phiếm và dẫn dắt người dùng quay lại chủ đề chính một cách tự nhiên.

## Kiến trúc

- **Backend**: FastAPI, phục vụ API và logic chính.
- **Frontend**: Gradio, hoạt động như một client mỏng (thin client) gọi API streaming.
- **Orchestrator**: LangGraph.
- **Models**: Ollama (`gpt-oss`, `bge-m3`, `phi-3`, etc.).
- **Lưu trữ**: SQLite/Postgres và ChromaDB.

## Quick start

1.  **Chạy Backend (FastAPI):**

    ```bash
    uv run uvicorn agent.main:app --reload --host 0.0.0.0 --port 8000
    ```

2.  **Chạy UI (Gradio client) trong một terminal khác:**

    ```bash
    uv run --with gradio ui/gradio_app.py
    ```

## Xem thêm
- `docs/architecture.md` — Chi tiết về kiến trúc hệ thống.
- `docs/langgraph_flow.md` — Mô tả chi tiết luồng xử lý của LangGraph và Agent.
- `docs/run_local.md` — Hướng dẫn đầy đủ để chạy dự án trên máy cục bộ.
- `docs/data_model.md` — Sơ đồ và mô tả các bảng dữ liệu.