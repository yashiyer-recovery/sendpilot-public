# SendPilot

A sales/email AI agent. Connect your mailbox (Gmail / Microsoft 365), upload a
document in almost any format, and SendPilot **extracts the recipient, subject,
and body** for each email, validates them, lets you **review and approve**, then
sends through your own account with an idempotent, rate-limited pipeline.

The differentiated core is the **extraction engine**: a deterministic
column-mapping path for spreadsheets (no per-row model cost) and a Claude
**structured-outputs** path for prose documents.

> Built from `SendPilot_Technical_PRD.pdf`. This repo is sequenced MVP-first
> (M0 → M1 → M2 → M4); see `/Users/yashiyer/.claude/plans/reactive-hatching-twilight.md`.

## Layout

```
apps/api      FastAPI backend + BFF + arq worker (Python 3.12)
apps/web      Next.js review UI (TypeScript)
packages/…    generated typed API client
infra/…       local dev shims (mock email provider, KMS notes)
```

## Quick start (local, no real accounts needed)

```bash
cp .env.example .env
docker compose up --build
# API:  http://localhost:8000   (/health, /docs, /metrics)
# Web:  http://localhost:3000
# The mock provider stands in for Gmail OAuth + sending, so the whole
# flow is exercisable without a real mailbox or Anthropic key.
```

## Status

- **M0 — Foundations** ✅ tenancy + Postgres RLS, Gmail OAuth + encrypted token
  vault, document upload + AV scan, observability baseline. Verified via
  `tests/smoke_m0.py` + RLS isolation test.
- **M1 — Single-send MVP** ✅ extraction engine (deterministic tabular path +
  Claude narrative path), validation/suppression/confidence gating,
  review/approve API + Next.js review UI, idempotent queue-backed Gmail send,
  unsubscribe. Verified via `tests/smoke_m1.py` (Excel → extract → approve →
  send → suppression), the chaos/idempotency test, and the extraction eval gate.
- **M2 — Scale & providers** ✅ Microsoft 365 provider (Graph send) behind the
  same abstraction, bounce/complaint/reply ingestion via a normalized webhook
  (hard bounce → suppression), analytics rollups, and the quality circuit
  breaker. Verified via `tests/smoke_m2.py` + bounce/circuit-breaker DB tests.
- **M4 — Hardening** (partial): retention purge cron, log redaction + prompt-
  injection-safe extraction, eval-gated CI with a frontend build job. Remaining:
  anti-abuse content screening, full OpenTelemetry tracing + alerts, load tests,
  OpenAPI-generated typed client + contract tests, SOC2/GDPR export/delete.

### Verify locally

```bash
docker compose up -d db redis minio mock-provider migrate api worker
# end-to-end (needs httpx + openpyxl):
API_BASE=http://localhost:8080 python apps/api/tests/smoke_m1.py
# tests + gates:
docker compose exec -e ENV=test api pytest -q -m "not live"
docker compose exec api python tests/eval/run_eval.py
```

> Note: on this dev host the API is published on **:8080** and the mock provider
> on **:9100** (set in `.env` via `API_PORT`/`MOCK_PORT`) because :8000/:5432
> were occupied; defaults are :8000/:9100.

## Development

```bash
cd apps/api
uv sync                       # or: pip install -e ".[dev]"
ruff check src && mypy src
pytest                        # db/integration tests need DATABASE_URL (see docker compose)
```
