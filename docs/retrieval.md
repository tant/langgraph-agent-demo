# Chiến lược Retrieval (ngắn gọn và đủ ý)

Mục tiêu: tìm các đoạn hội thoại/thông tin liên quan để augment prompt và cải thiện chất lượng trả lời.

Chiến lược tóm tắt: ưu tiên lấy context từ same-conversation (chat history); nếu coverage/confidence không đủ, mở rộng truy vấn sang knowledge base (ChromaDB) dùng embeddings `bge-m3` và áp dụng vector search + re-rank (vector score + heuristics + optional lexical/BM25).

## Thành phần & thông số chính
- Vector store: ChromaDB (local) — path `./database/chroma_db/`.
- Embedding model: `bge-m3` (1024-d) via Ollama.
- Chunk size: 200–512 tokens.
- Retriever: vector search (cosine/inner-product) + optional lexical fallback (BM25).
- Re-rank: top-N → re-rank bằng score + heuristics (freshness, same-conversation boost).
- Context budget: mặc định chọn top-K = 3; có thể mở rộng (3–10) theo token budget và confidence của retriever.

## Quy tắc Top-K (rõ ràng)
- Mặc định: top-K = 3 — đủ để cung cấp ngữ cảnh hữu ích mà không quá tốn token.
- Mở rộng động: nếu token budget còn và retriever confidence cao, mở rộng incremental tới tối đa 10 (3 → 5 → 8 → 10); số thực tế phụ thuộc vào tổng token khi ghép prompt.
- Chiến lược re-rank: lấy một batch lớn ban đầu từ vector query (ví dụ N = 20), sau đó re-rank theo score + heuristics và chọn top-K cuối cùng để đưa vào prompt.

## Luồng ngắn (concise)
1. Nhận message → chunk nếu cần.
2. Tạo embedding cho chunk bằng `bge-m3` → enqueue job (recommended) hoặc sync for realtime.
3. Upsert vectors vào Chroma với metadata (message_id, conversation_id, user_id, created_at).
4. Khi trả lời: truy vấn vector store → re-rank → assemble top-K context → đưa vào prompt.

Note: tốt nhất lấy một batch lớn ban đầu (ví dụ N=20) rồi re-rank để chọn top-K=3 cho prompt; điều này giúp tránh bỏ lỡ context quan trọng gần ngưỡng.

## ChromaDB — khuyến nghị cụ thể
- Collection naming: per-environment (e.g., `conversations_dev`, `conversations_prod`) hoặc per-tenant nếu cần phân vùng mạnh.
- Upsert: batch upsert, idempotent (key = `{message_id}#chunk_{i}`).
- Querying: hỗ trợ metadata filters (conversation_id, user_id, time window) để tăng precision.
- Persistence: snapshot `./database/chroma_db/` định kỳ; backup metadata cùng lúc.

## Caching, metrics, hiệu năng
- Cache retriever results ngắn hạn (Redis) cho truy vấn lặp.
	- Note: Redis caching for retriever results is recommended in production; in development use an in-process cache or skip caching.
- Batch embeddings/upserts để tăng throughput.
- Metrics: vector query time, embedding latency, cache hit-rate, recall/precision.

## Notes & best-practices
- Hybrid retrieval: kết hợp vector + lexical (BM25) khi cần recall từ tài liệu text.
- Re-ranking: sau initial vector search, re-rank to prefer recent or same-conversation segments.
- Error handling: embedding/upsert jobs cần retry/backoff; mark failures in metadata để retry manual.

## Quick decisions (chốt)
- Embedding: `bge-m3` (1024-d)
- Vector store: ChromaDB local (path `./database/chroma_db/`)
- Chunking: 200–512 tokens
- Top-K: mặc định = 3; mở rộng động tới 10 theo token budget và retriever confidence
