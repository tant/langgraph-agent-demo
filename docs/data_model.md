# Mô hình dữ liệu (gọn, đủ ý)

Mục tiêu: mô tả ngắn gọn các bảng chính, mapping tới ChromaDB (local) và các quy tắc lưu/xoá.

## Bảng chính (tóm tắt)
- `conversations`: id (uuid), user_id, created_at, last_active_at, metadata
- `messages`: id (uuid), conversation_id, sender, text, tokens_estimate, created_at, metadata
- `feedback_logs`: id (uuid), conversation_id, message_id, feedback_type (e.g., "👍", "👎"), user_comment (text, optional), created_at

(Embeddings không lưu trực tiếp trong SQL — dùng ChromaDB để index vectors.)

## Bảng mới: `feedback_logs`

Bảng này được thêm vào để hỗ trợ **Tính năng Vòng lặp Phản hồi (Feedback Loop)**.

- **`id`**: Khóa chính của bản ghi phản hồi.
- **`conversation_id`**: Liên kết phản hồi với một cuộc trò chuyện cụ thể.
- **`message_id`**: Liên kết phản hồi với một tin nhắn cụ thể của chatbot.
- **`feedback_type`**: Lưu trữ loại phản hồi trực tiếp (ví dụ: "👍" hoặc "👎").
- **`user_comment`**: Lưu trữ bình luận chi tiết của người dùng nếu họ cung cấp sau khi đưa ra phản hồi tiêu cực.

## ChromaDB mapping
- ChromaDB path: `./database/chroma_db/` (local persistent store)
- Mapping cơ bản:
  - messages.id -> chroma vector id
  - messages.metadata -> chroma metadata (conversation_id, user_id, created_at)
- Embedding dimension: 1024 (model `bge-m3`)

## Chunking & upsert
- Granularity: chunk 200–512 tokens nếu message quá lớn.
- Upsert: batch upsert, idempotent (dùng `{message_id}#chunk_{i}` làm key).
- Delete: khi xóa message/conversation, xóa vector tương ứng khỏi Chroma.

## Backup & consistency
- Backup đồng bộ: snapshot `./database/chroma_db/` cùng với DB metadata backup.
- Khi restore, đảm bảo mapping messages <-> vectors nhất quán (kiểm tra tồn tại `message_id`).

## Quick notes
- DB prod: Postgres + pgvector (nếu muốn SQL vector index); dev: SQLite + Chroma local.
- Lưu metadata đầy đủ để hỗ trợ filters và re-ranking.