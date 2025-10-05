# Contributing to **North Star**

> **Where to put this file?**
>
> Place this `CONTRIBUTING.md` **at the root of your repository** — the same folder you open with `code .` (e.g., your `northstar/` folder). This ensures GitHub, Cursor, and other tools surface it automatically. Put your `.cursorrules` in this same root as well.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Repository Structure](#repository-structure)
- [Branching & PRs](#branching--prs)
- [Local Development](#local-development)
- [Environment & Secrets](#environment--secrets)
- [Running the API](#running-the-api)
- [Seeding the Database](#seeding-the-database)
- [Quality: Lint, Format, Types](#quality-lint-format-types)
- [Architecture Guardrails (SOLID)](#architecture-guardrails-solid)
- [Auth & RBAC Invariants](#auth--rbac-invariants)
- [Configuration Invariants](#configuration-invariants)
- [Endpoint Contracts](#endpoint-contracts)
- [Ports/Adapters Rules](#portsadapters-rules)
- [Retrieval Rules](#retrieval-rules)
- [Agent Tools & Planner](#agent-tools--planner)
- [Testing & Smoke Scripts](#testing--smoke-scripts)
- [Commit Messages](#commit-messages)
- [Security Checklist](#security-checklist)
- [.cursorrules](#cursorrules)
- [Troubleshooting](#troubleshooting)

---

## Project Overview

**North Star** is a policy-aware, multi-tenant, agentic platform for:
1. **Strategic Staffing**
2. **Personalized Onboarding**
3. **Continuous Skill Intelligence**

Core stack:
- **FastAPI** (backend)
- **PostgreSQL** (RDS or local) for relational data
- **Qdrant** (Cloud) for vectors
- **Upstash Redis** (cloud) for queue/rate-limiting
- **Cerebras Maverick** (LLM planner) + Atlassian (Jira, Confluence) integrations

---

## Repository Structure

```
backend/
  app/
    adapters/          # IO integrations (Qdrant, BGE, Jira, Confluence, Cerebras)
    application/       # Business logic (staffing, onboarding, ingestion)
    domain/            # SQLAlchemy models + Pydantic schemas
    middleware/        # Auth + Audit middlewares
    ports/             # Thin facades exposing use cases to routes
    routes/            # FastAPI endpoints (import only from ports + schemas)
    utils/             # chunking, hashing, idempotency, time helpers
    main.py            # app factory + router includes + tool registration
  worker/
    handlers/          # async skill extraction + webhook processors
    queue.py           # redis queue support
    main.py            # worker entrypoint
```

**Key rule:** Routes → **Ports** → **Application** → **Adapters**. Domain is pure models/schemas.

---

## Branching & PRs

- **main**: stable, deployable
- **feat/***: new features
- **fix/***: bug fixes
- **chore/***: tooling, docs

PR requirements:
- Describe the problem, solution, and risk
- Include before/after behavior
- Reference issues if any
- Pass lint, type check, tests

---

## Local Development

Prereqs:
- Python 3.12+ (venv recommended)
- `psql` client available
- Qdrant Cloud cluster + API key
- Upstash Redis URL + token
- RDS (or local Postgres) reachable

Setup:

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate

pip install -r requirements.txt
# or: pip install -e backend
```

---

## Environment & Secrets

Create `.env` at repo root (same folder as this file) by copying `.env.example` and filling values:

```
JWT_SECRET=<64+ random chars>
JWT_AUD=northstar

POSTGRES_HOST=<your-rds-endpoint>
POSTGRES_PORT=5432
POSTGRES_DB=northstar
POSTGRES_USER=postgres
# Do not add quotes around the password. On Windows PowerShell, prefer loading from .env or escape any $ characters.
POSTGRES_PASSWORD=<your-password>

QDRANT_URL=<your-qdrant-cloud-url>
QDRANT_API_KEY=<your-qdrant-cloud-key>

REDIS_URL=<your-upstash-redis-connection-url>

CEREBRAS_API_KEY= # optional for /onboarding + /agent with jira/confluence
ATLASSIAN_BASE_URL=
ATLASSIAN_EMAIL=
ATLASSIAN_API_TOKEN=

GITHUB_WEBHOOK_SECRET=change_me
```

Never hardcode secrets in code or tests. Always read via `app.config.settings`.

---

## Running the API

```bash
# from backend/ directory:
uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

Worker (optional unless testing webhooks/skills):
```bash
python -m backend.worker.main  # or equivalent worker entry command
```

---

## Seeding the Database

Use the provided seed SQL to create a tenant, projects, users, and a developer:

```bash
psql "host=$POSTGRES_HOST port=$POSTGRES_PORT dbname=$POSTGRES_DB user=$POSTGRES_USER password=$POSTGRES_PASSWORD sslmode=require" -f seed.sql
```

Verify IDs:
```sql
SELECT id, key FROM project ORDER BY id;
SELECT id, display_name FROM developer ORDER BY id;
```

---

## Quality: Lint, Format, Types

- **ruff** for lint: `ruff check backend`
- **black** for format: `black backend`
- **mypy** for types: `mypy backend`

These should be green before you open a PR.

---

## Architecture Guardrails (SOLID)

- **S**ingle Responsibility: Routes just translate HTTP ⇄ Ports. No business logic in routes.
- **O**pen/Closed: Add capabilities by new adapters or port funcs; don’t modify planner core.
- **L**iskov: Keep port signatures stable; return documented schemas.
- **I**nterface Segregation: Ports expose minimal cohesive operations.
- **D**ependency Inversion: Routes depend on ports/schemas; ports depend on application; application depends on adapters.

---

## Auth & RBAC Invariants

- **Always** read `Authorization: Bearer <JWT>` header (never querystring).
- Decode in `AuthMiddleware`; dependencies `get_current_user()` & `require_role()` use `request.state.user`.
- Enforce **tenant** boundaries and **project-level** access in **ports** (closest to data). Use 404 on cross-tenant resources, 403 on role violations.

---

## Configuration Invariants

- No hardcoded URLs/tokens/collection names.
- Read everything from `app.config.settings` (env-driven).
- If you add a new flag, add it to `.env.example`, `settings`, and docs.

---

## Endpoint Contracts

All responses must use schemas from `app/domain/schemas.py`. Endpoints in `routes/` must:
- Import **ports** only (`from app.ports.retriever import rag_search, api_response`, etc.)
- Enforce RBAC & tenancy (usually the port will perform the final check)
- Return the exact Pydantic response model described by OpenAPI
- Log start/end with request id, tenant; never log secrets or full JWTs

---

## Ports/Adapters Rules

- **Routes → Ports** (never directly call application/adapters from routes).
- Ports orchestrate: RBAC guard, dedupe, evidence building, stable shapes.
- Adapters only do IO (Qdrant, BGE, Jira/Confluence, Cerebras).

---

## Retrieval Rules

- `/retrieve` → `app.ports.retriever`:
  - **No hardcoded collection names**; build via a helper using `tenant_id` + `project_key`.
  - Support `strategy=["qdrant","rrf"]`.
  - Over-fetch then **dedupe by `chunk_id`** (fallback: stable text hash).
  - Build evidence internally (not returned by the route) to support planner tools.
  - Return `RetrieveResp(results=[...])` only.

---

## Agent Tools & Planner

- Tools are defined and **registered at startup** (`register_all_tools()`), otherwise `execute_plan` has an empty toolbox.
- Tool names: `"rag_search"`, `"jira_epic"`, `"confluence_page"`.
- Tool wrappers accept `user_claims` and call `policy_bus.enforce(tool, role)` before invoking adapters.
- Planner must return **valid JSON** (no markdown fences) matching schema hint.

---

## Testing & Smoke Scripts

Quick smoke (PowerShell):

```powershell
$BASE = "http://localhost:9000"
$tokenResp = Invoke-RestMethod -Method POST -Uri "$BASE/auth/token?username=po_admin&password=x"
$TOKEN = $tokenResp.access_token
$H = @{ "Authorization" = "Bearer $TOKEN" }

# Create PX (idempotent)
Invoke-RestMethod -Method POST -Uri "$BASE/projects?key=PX&name=Realtime%20Pricing&description=Pricing%20Platform" -Headers $H

# Upload PX.md (ensure file exists in current dir)
curl.exe -X POST -H "Authorization: Bearer $TOKEN" -F "project_key=PX" -F "file=@PX.md;type=text/markdown" "$BASE/upload"

# Retrieve
Invoke-RestMethod -Method POST -Uri "$BASE/retrieve" -Headers ($H + @{ "Content-Type"="application/json" }) -Body (@{ query="pricing api kafka"; targets=@("PX"); k=6 } | ConvertTo-Json)
```

Add pytest suites under `backend/tests/` (httpx TestClient).

---

## Commit Messages

Follow **Conventional Commits**:
- `feat: add PX retrieval strategy rrf`
- `fix: enforce tenant guard in upload route`
- `chore: bump ruff`
- `docs: add smoke script`

---

## Security Checklist

- Never log secrets, raw JWTs, or evidence payloads.
- Use `sslmode=require` for Postgres (RDS).
- Qdrant Cloud: always pass API key in header.
- Rotate tokens frequently; use `.env` instead of hardcoding.
- For webhooks, verify `X-Hub-Signature-256` with your `GITHUB_WEBHOOK_SECRET`.

---

## .cursorrules

Place a `.cursorrules` in the repo root, e.g.:

```
# Routes must import from app.ports.*, return domain schemas, and enforce RBAC/tenancy
- No hardcoded URLs/keys; use app.config.settings
- Register agent tools at startup
- Retrieval port must support strategy ["qdrant","rrf"] and dedupe by chunk_id
- Do not modify core business math in staffing_service without approval
- Add acceptance tests for each endpoint
```

---

## Troubleshooting

- **401 Unauthorized**: Ensure `Authorization: Bearer <token>` header; refresh token via `/auth/token`.
- **403 Forbidden**: Role mismatch (use PO for admin paths) or project not in `accessible_projects`.
- **404**: Cross-tenant access attempted or resource doesn’t exist.
- **500/502**: Check logs for bad imports (`retreiver.py` vs `retriever.py`), missing envs, or external IO failures.
- **Upload fails**: Ensure file path exists; use absolute path or place file in current dir.
- **Qdrant**: Verify `QDRANT_URL` and `QDRANT_API_KEY` envs; cluster healthy.
- **DB**: Run seed.sql and confirm IDs with psql.
