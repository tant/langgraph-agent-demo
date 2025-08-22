# Bảo mật & Quyền riêng tư

## Mạng & Giao thức
- Nếu dịch vụ hoặc Ollama được *exposed* qua mạng, bật TLS cho mọi kết nối (client ↔ API, API ↔ Ollama nếu Ollama reachable qua network).
- Nếu Ollama chạy hoàn toàn trên máy local (localhost) và không mở port ra ngoài, TLS cho kết nối tới Ollama là không bắt buộc; vẫn giới hạn truy cập bằng firewall hoặc reverse-proxy nếu có khả năng truy cập mạng.
- Production: cân nhắc mTLS cho giao tiếp giữa services khi cần bảo mật nội bộ và least-privilege.

## Dữ liệu
- Mã hóa at-rest cho dữ liệu nhạy cảm hoặc field-level encryption.
- Masking/ redaction cho PII trước khi lưu hoặc gửi tới models; tránh lưu raw PII trong embeddings.
- Retention policy configurable (ví dụ: 90 ngày) và có cơ chế purge/soft-delete.

## Xác thực & Ủy quyền
- Token-based auth (opaque tokens) qua header `X-API-Key` là mặc định cho API.
- Token lifecycle: support revocation, short-lived tokens for sensitive ops, and separate admin keys (audited).
- RBAC: giới hạn hành động admin (delete/export) cho admin role; yêu cầu MFA/2FA cho thao tác destructive trong production.

## Secrets & supply-chain
- Production: use KMS / Vault (AWS/GCP/Azure/HashiCorp) for secrets; keep only references in env.
- Pin dependencies, run SCA in CI, and enable Dependabot or equivalent to track vulnerabilities.

## Throttling & brute-force
- Rate limiting: per-user + global; production uses Redis for distributed limits, local dev may use in-process limiter.
- Lockout policy for repeated failed auth attempts.

## Prompt & input safety
- Validate and sanitize user inputs; isolate prompt templates (no string-concat of raw user prompt into prompt templates without guardrails).
- Run content-safety checks (classifier) for unsafe content and apply redaction/blocking policies.

## Vector privacy
- Restrict vector queries by tenant/conversation metadata.
- Avoid indexing raw PII; tag and redact sensitive vectors; restrict delete/export operations.

## Audit & Incident Response
- Store immutable audit logs for critical actions; include actor, request_id, timestamp.
- Alerts: auth anomalies, elevated DLQ rates, embedding failure spikes.
- IR playbook: steps for containment, evidence preservation, and notification.

## Dev vs Production (short)
- Local dev: Ollama on localhost → TLS to Ollama optional; Redis optional; debug flags off in prod; tighten CORS.
- Production: enable Redis, TLS/mTLS as required, use KMS/Vault, enforce RBAC & MFA for admins.
