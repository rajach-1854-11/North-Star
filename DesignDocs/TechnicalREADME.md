# Technical Deep Dive

This document links subsystems to code with regeneration traceability via `scripts/generate_arch_docs.py`.

## End-to-End Flow
- HTTP requests enter FastAPI routers (`app/routes/*`).
- Dependencies inject services (`app/services/*`) and policy guards (`app/policy/*`).
- Adapters (`app/adapters/*`) integrate with GitHub, Jira, Confluence, Qdrant, and LLM APIs.
- Persistence relies on SQLAlchemy models (`app/domain/models.py`) and Redis-backed queues.
- Worker handlers (`worker/handlers/*`) replay queued events for idempotent updates.
- Sequence references: see `Sequences/` for per-action breakdowns.

## Module Breakdown
- **Routes:** Request validation, rate limits, audit emission.
- **Services:** Domain operations for assignments, onboarding, retrieval, audits.
- **Policy:** Enforcement pipelines, deny lists, isolation proof emitters.
- **Agentic:** Planner/executor loop, skill extraction, tool registry.
- **Adapters:** Integrations across GitHub, Jira, Confluence, Qdrant, LLM providers.
- **Ports:** Interfaces consumed by services for substitution-friendly architecture.
- **Worker:** Job queue orchestrators and webhook processors.

## Policies & Identity
- RBAC and policy bus lives in `app/policy/`.
- Identity resolution handled by services under `app/services/identity_*`.
- `IntegrationEventLog` + `AttributionWorkflow` enforce idempotency and traceability.

## Persistence & Storage
- SQLAlchemy models cover tenants, users, projects, skills, attribution, audits (see ERD).
- Migrations (if present) in `app/application/migrations`.
- Redis for caching/queues; Qdrant for embeddings; local FS for isolation proofs.

## Configuration Matrix
| Variable | Default | Purpose |
| --- | --- | --- |
| ENV | dev | Runtime mode |
| DATABASE_URL | - | Optional full Postgres URL |
| POSTGRES_HOST | (required) | Postgres hostname |
| REDIS_URL | - | Enables Redis-backed queues |
| QUEUE_MODE | redis | `redis` or `direct` execution |
| LLM_PROVIDER | cerebras | Chooses LLM backend (openai/cerebras) |
| QDRANT_URL | (required) | Vector DB endpoint |
| POLICY_ENFORCEMENT | strict | Policy guardrail mode |
| TRACE_MODE | false | Enables OpenTelemetry tracing |

## Observability
- Logging config at `app/logging_setup.py` (structured loguru configuration).
- OpenTelemetry instrumentation under `app/instrumentation/`; exporters configured via env.
- Audit log persisted via `app/domain/models.py::AuditLog`.

## Testing
- Run `pytest` from `North-Star/Src/backend`.
- Integration fixtures under `tests/` and `skill_tests/`.
- Use `.env.local` to override secrets for test runs (script loads automatically).

## Operations
- Deploy API with `uvicorn`/ASGI server behind nginx (see `docker-compose.yml`).
- Worker binds to Redis queue `events`; ensure Redis reachable for scaling out.
- Health endpoints exposed under `/health` and `/ready` (see routers).
- Scaling: horizontally scale API/worker separately; share Postgres, Redis, Qdrant.
