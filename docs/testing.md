# Kiểm thử & Đảm bảo chất lượng (gọn, hành động)

## Mục tiêu
Ngắn, có thể thực thi: đảm bảo correctness (unit), integration (message→worker→vector), performance (load), và resilience (chaos).

## Unit tests
- Test business logic: session management, chunking, retriever ranking, idempotent upsert.
- Run fast, isolated: pytest, mock external dependencies (Ollama, Chroma client).

## Integration tests
- End-to-end: send message -> worker processes embedding -> vector exists in Chroma -> retrieval returns context.
- Test env: use SQLite + in-memory Chroma or testcontainers for Chroma/Ollama in CI.
- Deterministic CI rules: seed DB, teardown between tests, set timeouts, avoid relying on external Redis in dev.

## Mocks / Fixtures
- Provide fixtures to mock Ollama responses for generation and embeddings for speed in unit/CI tests.
- Option: run a real local Ollama container in integration tests for higher fidelity.

## Contract / Security tests
- API contract tests: validate OpenAPI responses, auth behavior, and error codes.
- Security tests: prompt-injection checks, content-safety classifier smoke tests, dependency SCA scans in CI.

## Load tests (example thresholds)
- Tooling: k6 or JMeter.
- Example target: 100 concurrent users; validate P95 ACK < 200ms; queue_length stays < 100 during sustained load.
- Rate-limit validation: verify 5 req/s per user enforced and returns 429 when exceeded.

## Chaos & resilience
- Scenarios: worker restarts, simulated Redis outage (run in integration environment with Redis), DLQ behavior.
- Local/dev: if Redis not available, run no-Redis mode and validate degraded behavior.

## CI pipeline (recommended stages)
1. Install deps
2. Run unit tests (fast)
3. Run smoke integration tests (start minimal services via testcontainers or local containers)
4. Run contract tests
5. Nightly/performance: run load and chaos tests separately (long-running)

## Flakiness & best-practices
- Isolate slow tests from unit/fast suites.
- Use retries for non-deterministic infra in CI with limits and record flake metrics.
- Set sensible timeouts and resource limits for tests.

## Example commands
```bash
# unit
pytest -q --maxfail=1 tests/unit

# smoke integration (example using pytest markers)
pytest -q -m integration

# load (k6)
k6 run scripts/load_test.js
```

## Quick checklist for PRs
- Add unit tests for new logic.
- If behavior touches embedding/indexing, add an integration smoke test that asserts vector upsert.
- Run SCA scanner in CI and include security checklist for prompt handling.
