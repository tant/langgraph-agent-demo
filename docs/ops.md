# Vận hành & Monitoring

# Vận hành & Monitoring (gọn, hành động)

## Metrics & Observability
- Export Prometheus metrics: request_latency, embedding_latency, vector_query_time, queue_length, DLQ_size.
- Structured logs (JSON) with request_id, conversation_id, user_id.
- Tracing: OpenTelemetry across API → worker → Ollama.

## SLOs & Alerts (examples)
- SLO: P95 request ACK < 200ms.
- Alert if queue_length > 100 for 5m.
- Alert if DLQ_size > 0 or embedding failure rate spikes.

## Backups & Restore
- Daily DB snapshot + nightly Chroma snapshot; retention: 30/90 days (configurable).
- Weekly restore test in staging to validate backups.
- Run reconciliation script after restore to re-link messages ↔ vectors.

## Deployment & Rollout
- Docker images with immutable tags; use k8s readiness/liveness probes and rolling or canary deploys.
- Health checks: liveness + readiness endpoints for API and workers.

## Secrets & config
- Use KMS/Vault for production secrets; do not store secrets in repo or plain env files.

## Runbook (short)
1. On DLQ alert: inspect failed jobs → attempt safe requeue for transient errors.
2. If data corruption suspected: restore latest snapshot to staging, run reconciliation, then promote.
3. For embedding spikes: scale embedding workers or disable sync embedding path temporarily.

## CI / Release pipeline
- Stages: build image → unit tests → smoke integration → migration checks → canary/staging verification → prod rollout.
- Nightly: performance/load tests and SCA scans.

## Ops commands (examples)
```bash
# DB snapshot (example)
pg_dump -Fc "$DATABASE_URL" > "/backups/db-$(date +%F).dump"

# snapshot Chroma (example)
tar czf "/backups/chroma-$(date +%F).tgz" ./database/chroma_db

# requeue DLQ (example)
python scripts/requeue_dlq.py --limit 100
```

## Ownership
- On-call: owner for DLQ/embedding failures; specify pager duty or contact list in runbook.
