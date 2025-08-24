# Kế hoạch Triển khai Chi tiết - Phase 2

Đây là kế hoạch hành động chi tiết để triển khai các tính năng của Phase 2, dựa trên các tài liệu đặc tả đã được cập nhật. Sử dụng checklist này để theo dõi tiến độ công việc.

## Giai đoạn 0: Chuẩn bị & Cấu trúc (Setup & Scaffolding)

Mục tiêu: Chuẩn bị nền tảng cần thiết trước khi viết logic chính.

- [ ] **Cơ sở dữ liệu**:
    - [ ] Cập nhật schema của cơ sở dữ liệu để thêm bảng `feedback_logs` như trong `docs/data_model.md`.
    - [ ] Chạy migration để áp dụng thay đổi.
- [ ] **Cấu trúc thư mục**:
    - [ ] Tạo các file hoặc placeholder cho các thành phần mới nếu cần.
- [ ] **Công cụ (Tools)**:
    - [ ] Viết các hàm "giả" (stub functions) cho từng công cụ được định nghĩa trong `docs/langgraph_flow.md` (ví dụ: `tra_cuu_thong_tin_bao_hanh`, `tim_kiem_san_pham`, etc.). Các hàm này sẽ trả về dữ liệu giả để có thể xây dựng luồng chính trước.

## Giai đoạn 1: Triển khai Backend & Logic Cốt lõi

Mục tiêu: Xây dựng toàn bộ logic phía server.

- [ ] **Cập nhật Luồng LangGraph**:
    - [ ] Implement lại kiến trúc graph trong `agent/langgraph_flow.py` để khớp với sơ đồ trong `docs/langgraph_flow.md`, bao gồm các node: `greeting_node`, `router`, `agent_loop`, và `farewell_node`.
- [ ] **Triển khai Agent và các Công cụ**:
    - [ ] Hoàn thiện logic cho từng hàm công cụ đã tạo ở Giai đoạn 0, kết nối chúng với cơ sở dữ liệu và RAG thật.
    - [ ] Tích hợp các công cụ này vào `agent_loop` của LangGraph.
    - [ ] Implement logic xử lý trò chuyện phiếm và dẫn dắt nâng cao.
- [ ] **Triển khai API Streaming**:
    - [ ] Trong `agent/main.py`, tạo endpoint `POST /chat/stream` sử dụng `StreamingResponse` của FastAPI.
    - [ ] Kết nối endpoint này với luồng LangGraph đã cập nhật để có thể stream phản hồi về cho client.
- [ ] **Triển khai Logic Phản hồi (Feedback)**:
    - [ ] Tạo một endpoint API mới, ví dụ `POST /messages/{message_id}/feedback`.
    - [ ] Endpoint này sẽ nhận `feedback_type` (và `user_comment` nếu có) từ client và lưu vào bảng `feedback_logs`.
- [ ] **Triển khai Hỗ trợ Đa ngôn ngữ**:
    - [ ] Tích hợp logic nhận diện và chuyển đổi ngôn ngữ vào `router` hoặc một node chuyên dụng trong LangGraph.
    - [ ] Đảm bảo trạng thái ngôn ngữ được lưu và sử dụng cho các prompt.

## Giai đoạn 2: Triển khai Giao diện Người dùng (Frontend)

Mục tiêu: Cập nhật UI để hỗ trợ các tính năng backend mới.

- [ ] **Tích hợp Streaming**:
    - [ ] Trong `ui/gradio_app.py`, sửa đổi logic gọi API để kết nối tới endpoint `/chat/stream`.
    - [ ] Cập nhật UI để hiển thị từng chunk dữ liệu ngay khi nhận được, tạo hiệu ứng gõ chữ.
- [ ] **Thêm Chức năng Phản hồi**:
    - [ ] Thêm các nút 👍/👎 vào bên cạnh mỗi câu trả lời của chatbot trong giao diện Gradio.
    - [ ] Viết logic để khi người dùng bấm vào các nút này, nó sẽ gọi đến API feedback đã tạo ở Giai đoạn 1.

## Giai đoạn 3: Tích hợp & Kiểm thử Toàn diện

Mục tiêu: Đảm bảo tất cả các thành phần hoạt động chính xác cùng nhau.

- [ ] **Cập nhật Unit Tests**:
    - [ ] Viết và cập nhật unit test cho các node mới, các hàm công cụ, và logic API.
- [ ] **Viết Integration Tests**:
    - [ ] Viết kịch bản kiểm thử tích hợp cho luồng streaming end-to-end.
    - [ ] Viết kịch bản kiểm thử cho việc gửi và lưu trữ feedback.
    - [ ] Viết kịch bản kiểm thử cho việc chuyển đổi ngôn ngữ.
- [ ] **Kiểm thử Thủ công (Manual E2E Testing)**:
    - [ ] Mở trình duyệt, tương tác với giao diện Gradio và kiểm tra tất cả các kịch bản:
        - [ ] Luồng hội thoại có diễn ra đúng như thiết kế không?
        - [ ] Streaming có mượt mà không?
        - [ ] Feedback có được lưu lại không?
        - [ ] Chuyển đổi ngôn ngữ có hoạt động không?
        - [ ] Các công cụ có trả về kết quả đúng không?

## Giai đoạn 4: Hoàn thiện & Dọn dẹp

Mục tiêu: Đóng gói và dọn dẹp dự án.

- [ ] **Review lại toàn bộ Code**:
    - [ ] Tổ chức một buổi review code để đảm bảo chất lượng, sự nhất quán và tối ưu hóa.
- [ ] **Review và Chốt Tài liệu**:
    - [ ] Đọc lại tất cả các tài liệu một lần cuối để đảm bảo chúng khớp 100% với sản phẩm đã triển khai.
- [ ] **Dọn dẹp**:
    - [ ] Xóa các file đặc tả nháp (`docs/phase2-*.md`) để tránh nhầm lẫn trong tương lai.
    - [ ] Xóa các file hoặc code không còn sử dụng.
