# Agent Backend và Gradio Frontend: Trao Đổi Dữ Liệu Streaming Mượt Mà

## 1. Kiến trúc tổng quan
- **Backend (FastAPI + LangGraph Agent):**
  - Xử lý logic hội thoại, quản lý session, truy xuất dữ liệu (RAG, DB).
  - Cung cấp endpoint API hỗ trợ streaming (Server-Sent Events hoặc WebSocket).
- **Frontend (Gradio):**
  - Giao diện chat cho người dùng cuối.
  - Kết nối tới backend qua HTTP streaming, hiển thị tin nhắn AI theo thời gian thực.

## 2. Quy trình trao đổi dữ liệu
### 2.1. Khởi tạo session
- Khi người dùng mở giao diện, frontend gửi request tạo session mới (POST `/session` hoặc tương tự).
- Backend trả về `session_id` (UUID), frontend lưu lại để gửi kèm các message tiếp theo.

### 2.2. Gửi message và nhận streaming response
- Frontend gửi message (POST hoặc WebSocket) kèm `session_id`.
- Backend nhận message, bắt đầu xử lý và trả về response dạng streaming (chunked text hoặc event stream).
- Frontend nhận từng chunk và cập nhật UI theo thời gian thực.

#### Ví dụ API streaming (FastAPI):
```python
# agent/main.py
from fastapi.responses import StreamingResponse

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        async for chunk in agent.generate_stream(request):
            yield chunk  # chunk là text hoặc JSON
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

#### Ví dụ Gradio frontend sử dụng streaming:
```python
# ui/gradio_app.py
import gradio as gr
import requests

def stream_chat(message, session_id):
    url = "http://localhost:8000/chat/stream"
    with requests.post(url, json={"message": message, "session_id": session_id}, stream=True) as r:
        partial = ""
        for chunk in r.iter_lines():
            if chunk:
                partial += chunk.decode()
                yield partial

def main():
    with gr.Blocks() as demo:
        chatbot = gr.Chatbot()
        session_id = gr.State()
        msg = gr.Textbox()
        send = gr.Button("Send")
        send.click(stream_chat, inputs=[msg, session_id], outputs=chatbot)
    demo.launch()
```

## 3. Lưu ý kỹ thuật để tránh lỗi streaming
- **Backend:**
  - Đảm bảo endpoint trả về `StreamingResponse` đúng chuẩn, không buffer toàn bộ response trước khi gửi.
  - Xử lý exception trong generator, gửi thông báo lỗi qua stream nếu có.
  - Đảm bảo mỗi chunk nhỏ gọn, không quá lớn gây delay.
- **Frontend:**
  - Sử dụng `stream=True` (requests) hoặc tương đương để nhận từng chunk.
  - Xử lý timeout, retry nếu kết nối bị ngắt.
  - Cập nhật UI theo từng chunk, không đợi toàn bộ response.

## 4. Đoạn code mẫu kiểm tra streaming backend
```python
# scripts/test_ollama_stream.py
import requests

def test_stream():
    url = "http://localhost:8000/chat/stream"
    data = {"message": "Xin chào", "session_id": "test-session"}
    with requests.post(url, json=data, stream=True) as r:
        for chunk in r.iter_lines():
            if chunk:
                print(chunk.decode())

if __name__ == "__main__":
    test_stream()
```

## 5. Checklist phòng tránh lỗi phổ biến
- [x] Backend trả về `StreamingResponse` đúng chuẩn, không dùng `return JSONResponse` cho streaming.
- [x] Frontend nhận từng chunk, không đợi toàn bộ response.
- [x] Session_id được truyền đúng và kiểm tra hợp lệ ở backend.
- [x] Xử lý timeout, retry ở frontend nếu cần.
- [x] Log lỗi rõ ràng ở cả backend và frontend.

---
Tài liệu này cần được cập nhật khi có thay đổi về API hoặc framework streaming.
