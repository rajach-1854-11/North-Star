# North Star Architecture & Experience Compendium

This comprehensive README unifies the architecture overview, technical deep dive, and UX feature catalogue for North Star. You can regenerate the full pack from source any time with `scripts/generate_arch_docs.py`.

## Executive Summary

### North Star 🌟
*An agentic AI platform for large tech enterprises to intelligently staff projects, accelerate onboarding, and build a real-time map of their engineering talent. Built for the FutureStack'25 Hackathon.*

### The Problem
In large product companies like Meta and Google, staffing critical projects is slow, onboarding new engineers takes weeks, and understanding the true skill set of a 10,000-person engineering org is nearly impossible. Skill data is often self-reported and quickly becomes stale.

### The Solution
North Star acts as an intelligent co-pilot for engineering leadership. It uses an agentic RAG system to analyze vast amounts of internal project data, providing data-driven insights and automating complex workflows.

### Core Features
- **Strategic Staffing (IntelliStaff):** Recommends the best-suited engineers for new projects by analyzing their proven, evidence-based skills.
- **Personalized Onboarding (Aurora):** Automatically generates custom learning plans by comparing a new project's codebase with prior work, slashing time-to-productivity.
- **Continuous Skill Intelligence (IntelliStaff):** Passively analyzes PRs submitted, reviews required, comments received, rereviews(churn rate) and jira ticket closed to build a dynamic, real-time "Talent Graph" of the organization's capabilities.

### How It Works
I built the platform on a secure, multi-tenant RAG architecture. A planning agent deconstructs requests, and an execution agent retrieves context from project-specific knowledge bases to inform its analysis and actions, such as creating Jira epics or Confluence pages.


## Table of Contents
1. [Platform Overview](#platform-overview)
	- [Capabilities](#capabilities)
	- [Personas](#personas)
	- [Diagram Index](#diagram-index)
	- [Inventory Snapshot](#inventory-snapshot)
	- [Navigation Tips](#navigation-tips)
	- [Frontend Stack & Location](#frontend-stack--location)
	- [Backend Quickstart](#backend-quickstart)
	- [Glossary](#glossary)
2. [Technical Deep Dive](#technical-deep-dive)
	- [End-to-End Request Flow](#end-to-end-request-flow)
	- [Module Breakdown](#module-breakdown)
	- [Skill Graph Attribution](#skill-graph-attribution)
	- [Policies & Identity](#policies--identity)
	- [Persistence & Storage](#persistence--storage)
	- [Configuration Matrix](#configuration-matrix)
	- [Observability](#observability)
	- [Testing](#testing)
	- [Red-Team Tests & Enforcement — Implementation Summary](#red-team-tests--enforcement--implementation-summary)
	- [Operations](#operations)
3. [UX Feature Compendium](#ux-feature-compendium)

---

## Platform Overview

### Capabilities
- FastAPI HTTP APIs for staffing, onboarding, retrieval, and audit flows.
- RQ-backed worker for GitHub/Jira ingestion and skill attribution.
- Policy enforcement, identity resolution, and agentic planner components.
- **Agentic layer:** Custom planner/executor with a centralized policy bus (RBAC), per-tenant isolation, and immutable audits. No LangChain. Intent is rule-based (regex allow-list); ambiguous requests fall back to read-only RAG. (Optional LLM-assisted intent is advisory only, behind RBAC + schema checks.)

### Personas
- **Platform Admin:** Configures policies, integrations, and reviews audits.
- **Project Lead:** Requests onboarding plans and checks staffing readiness.
- **Developer:** Consumes onboarding tasks and skill insights.

### Diagram Index
- [C1 – Context](DesignDocs/C4/C1_Context.md)
- [C2 – Containers](DesignDocs/C4/C2_Containers.md)
- [C3 – Components](DesignDocs/C4/C3_Components.md)
- [C4 – Code](DesignDocs/C4/C4_Code.md)
- [ERD](DesignDocs/ERD/ERD.md)
- [Table Dictionary](DesignDocs/ERD/ERD_Table_Dictionary.md)

### Inventory Snapshot
- HTTP endpoints avialable: **18**
- Background handlers: **9**
- Machine-readable asset map: [inventory.json](inventory.json)

### Frontend Stack & Location
- **Stack:** Next.js 14 (App Router) + TypeScript; Tailwind CSS (Deep Space/Graphite theme); shadcn/ui; lucide-react; Framer Motion; Recharts; React Query; ky (30s timeout, one retry, JWT auto-attach); zod; jotai; React Hook Form.
- **Repo path:** `main-frontend/` (all UI code and pages).

### Navigation Tips
- Start with the C1→C4 diagrams for progressively deeper architectural views.
- Explore `Sequences/` for end-to-end request flows (one file per action).
- Consult the ERD set for relational modeling questions and constraints.
- Regenerate the full documentation bundle via `scripts/generate_arch_docs.py` to keep diagrams and indexes fresh.

### Backend Quickstart
1. Install dependencies: `pip install -e North-Star/Src/backend[dev]`
2. Provide `.env` values (see [Configuration Matrix](#configuration-matrix)).
3. Run API: `uvicorn app.main:app --reload`
4. Run worker: `python -m worker.main` when `QUEUE_MODE=redis`

### Glossary
- **Attribution Workflow:** Correlates PRs/issues to skill evidence.
- **Isolation Proof:** Policy proof package emitted for sensitive actions.
- **Planner/Executor:** Agentic orchestration for onboarding plan generation.
- **Retriever:** Vector search over Confluence/Jira content via Qdrant.

---

## Technical Deep Dive

### End-to-End Request Flow
- HTTP requests enter FastAPI routers (`app/routes/*`).
- Dependencies inject services (`app/services/*`) and policy guards (`app/policy/*`).
- Adapters (`app/adapters/*`) integrate with GitHub, Jira, Confluence, Qdrant, and LLM APIs.
- Persistence relies on SQLAlchemy models (`app/domain/models.py`) and Redis-backed queues.
- Worker handlers (`worker/handlers/*`) replay queued events for idempotent updates.
- Sequence references live under `Sequences/` for per-action breakdowns.

### Module Breakdown
- **Routes:** Request validation, rate limits, audit emission.
- **Services:** Domain operations for assignments, onboarding, retrieval, audits.
- **Policy:** Enforcement pipelines, deny lists, isolation proof emitters.
- **Agentic:** Planner/executor loop, skill extraction, tool registry.
- **Adapters:** Integrations across GitHub, Jira, Confluence, Qdrant, LLM providers.
- **Ports:** Interfaces consumed by services for substitution-friendly architecture.
- **Worker:** Job queue orchestrators and webhook processors.

### Agentic Orchestrator (No LangChain)

North Star uses a custom planner/executor instead of LangChain to guarantee multi-tenant RBAC, policy-gated tool use, and compliance-grade auditing.

**Why no LangChain?** I needed deterministic control over tool routing, tenant isolation, and audits. Those guarantees are easier with a minimal, explicit loop than a generic agent framework.

**What I built:**

- **Central policy bus:** every tool call goes through `policy_bus.enforce(tool, role)` (deny-by-default).
- **Tool registry at startup:** `register_all_tools()`, no dynamic exec.
- **Tenant isolation:** per-tenant Qdrant collections; ports re-check tenant on every read/write.
- **Immutable audits:** every ALLOW/DENY emits an audit record (zero side effects on DENY).

**Intent detection (current):** rule-based, not LLM.
- Regex triggers (e.g. `jira_epic`, `confluence_page`) + light parsing.
- Ambiguous phrases (e.g. "jira") fall back to read-only RAG.
- This is intentional hard-gating to prevent accidental writes.

**Example (intent → gated tool):**
```python
# chat_orchestrator.py (simplified)
if _JIRA_TRIGGER.search(lowered):      # requires explicit 'jira_epic'
    tool = "jira_epic"; explicit = True
elif _CONFLUENCE_TRIGGER.search(lowered):
    tool = "confluence_page"; explicit = True
else:
    tool = None  # falls back to read-only RAG

# Planner will only execute registered tools after:
policy_bus.enforce(tool, user.role)    # deny-by-default
```

**Summary:** I run an allow-list, regex-gated, audited agentic loop with strict RBAC. No LangChain is used.

### Skill Graph Attribution
- GitHub webhooks (PRs, reviews, comments) resolve repository mappings and developer identity per tenant/project, triaging any unknown repo or user so events are never silently dropped.
- Each event appends evidence to an `AttributionWorkflow`; finalization is idempotent and gated on “PR merged” plus the linked Jira issue moving to a configurable done state.
- Once finalized, we upsert developer skill deltas (score, confidence, evidence reference, last-seen) via `worker.handlers.skill_extractor.apply_skill_delta`, ensuring the talent graph reflects the latest proof.
- Every finalize emits tenant-tagged metrics/logs for observability, making drift and throughput visible to ops teams.

### Policies & Identity
- RBAC and the policy bus reside in `app/policy/`.
- Identity resolution is handled in `app/services/identity_*`.
- `IntegrationEventLog` and `AttributionWorkflow` enforce idempotency and traceability.

### Persistence & Storage
- SQLAlchemy models cover tenants, users, projects, skills, attribution, audits (see ERD).
- Migrations (if present) live in `app/application/migrations`.
- Redis backs caching/queues; Qdrant stores embeddings; local FS hosts isolation proofs.

### Configuration Matrix

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENV` | dev | Runtime mode |
| `DATABASE_URL` | – | Optional full Postgres URL |
| `POSTGRES_HOST` | (required) | Postgres hostname |
| `REDIS_URL` | – | Enables Redis-backed queues |
| `QUEUE_MODE` | redis | `redis` or `direct` execution |
| `LLM_PROVIDER` | cerebras | LLM backend (openai/cerebras) |
| `QDRANT_URL` | (required) | Vector DB endpoint |
| `POLICY_ENFORCEMENT` | strict | Policy guardrail mode |
| `TRACE_MODE` | false | Enables OpenTelemetry tracing |

### Observability
- Logging config at `app/logging_setup.py` (structured Loguru configuration).
- OpenTelemetry instrumentation lives under `app/instrumentation/`; exporters configured via env.
- Audit log persisted via `app/domain/models.py::AuditLog`.

### Testing
- Run `pytest` from `North-Star/Src/backend` for the full suite.
- Integration fixtures live under `tests/` and `skill_tests/`.
- Use `.env.local` to override secrets for test runs—autoloaded by the settings loader.

### Red-Team Tests & Enforcement — Implementation Summary

1. **Tenant Isolation Negative Tests**  
	_Implementation:_ Cross-tenant retrieval and publish attempts return explicit policy errors, preventing data exfiltration.  
	_Files:_ `Src/backend/tests/test_security.py`; `app/policy/`

2. **Policy-Gated Tool Use**  
	_Implementation:_ Planner requests are denied unless the tool is whitelisted, with denials fully audited and side effects blocked.  
	_Files:_ `Src/backend/app/ports/planner.py`; `Src/backend/tests/test_planner_sanitization.py`

3. **Ingestion Replay Safety**  
	_Implementation:_ Duplicate and out-of-order webhook deliveries short-circuit safely via idempotency checks.  
	_Files:_ `Src/backend/app/application/ingestion_service.py`; `tests/test_github_webhook.py`; `tests/test_jira_webhook.py`

4. **RBAC Proofs**  
	_Implementation:_ Table-driven role checks ensure only authorized personas can reach each API surface.  
	_Files:_ `Src/backend/tests/test_security.py`; `app/policy/`

5. **Budget/Backpressure**  
	_Implementation:_ Per-tenant concurrency caps and request budgets defend against resource exhaustion during hostile load.  
	_Files:_ `app/services/`; worker/adapters (see scaling notes in this README)

6. **Traceability**  
	_Implementation:_ End-to-end traces link planner steps, adapters, and worker activity for audit replay.  
	_Files:_ `app/instrumentation/`; `app/domain/models.py::AuditLog`; `Src/backend/tests/test_planner_sanitization.py`

### Operations
- Deploy the API behind nginx (see `docker-compose.yml`).
- Worker binds to Redis queue `events`; ensure Redis is reachable for scaling out.
- Health endpoints exposed under `/health` and `/ready`.
- Scale API and worker horizontally as needed; share Postgres, Redis, Qdrant.

---

## UX Feature Compendium

This dossier links every front-of-house capability to the API surface, RBAC contracts, data touchpoints, and background automations that make the UX behave as shipped. Cross-reference the C4 deck for structural context, the ERD/Table Dictionary for storage contracts, and the `Sequences/` directory for step-by-step call traces.

### Authentication & Session Bootstrap
- **Summary:** Issue signed JWTs so the SPA can call tenant-scoped APIs without re-authenticating.
- **Personas:** Admin, PO, BA, Dev
- **Entry Points:** `POST /auth/token` (`Sequences/seq_api__post_auth_token.md`)
- **RBAC:** Public endpoint; credentials validated against `user.password_hash`
- **Data Touchpoints:** Reads `user`, `developer`, `project`, `assignment`
- **Notes:** One-hour TTL tokens; developers scoped to self; invalid creds return generic 401.
- **Quality Coverage:** `tests/test_security.py::test_token_requires_valid_credentials`

### Admin User Management
- **Summary:** Tenant admins review and adjust teammate roles.
- **Personas:** Admin
- **Entry Points:** `GET /admin/users`, `PATCH /admin/users/{id}/role`
- **RBAC:** `require_role("Admin")`
- **Notes:** Unknown user → 404; illegal role → 422. Audit trails capture changes.
- **Quality Coverage:** `tests/test_admin_routes.py`

### Project Catalog Management
- **Summary:** Stand up and browse tenant projects that drive staffing/onboarding scopes.
- **Personas:** Admin, PO, BA, Dev (read-only)
- **Entry Points:** `POST /projects`, `GET /projects`, `GET /projects/{key}`
- **RBAC:** Create requires Admin/PO; list/view allow Admin/PO/BA/Dev
- **Notes:** Duplicate key → 409 with user-friendly message.
- **Quality Coverage:** `tests/test_project_routes.py`, `tests/test_project_read_routes.py`

### Assignment Lifecycle
- **Summary:** Track developer staffing to power access control and fit scoring.
- **Personas:** Admin, PO (write), BA (read)
- **Entry Points:** `POST /assignments`, `PATCH /assignments/{id}`, `GET /projects/{id}/assignments`
- **Notes:** Enforces tenant isolation; uses `uq_dev_proj` for uniqueness.
- **Quality Coverage:** `tests/test_assignment_routes.py`

### Staffing Recommendation Console
- **Summary:** Surface ranked developer candidates with scoring explanations.
- **Personas:** Admin, PO, BA
- **Entry Points:** `GET /staff/recommend?project_id=*`
- **Notes:** Pure SQL + application logic; returns weights for UX charts.
- **Quality Coverage:** `tests/test_staff_routes.py`, `skill_tests/test_skill_attribution.py`

### Onboarding Plan Workspace
- **Summary:** Generate a two-week onboarding plan and publish Jira/Confluence artifacts.
- **Personas:** Admin, PO
- **Entry Points:** `POST /onboarding/generate`
- **Notes:** Planner fallback triggers warning log; audit token `audit_ref="onboarding"` links actions.
- **Quality Coverage:** `tests/test_onboarding.py`, `tests/test_agent_publish.py::test_onboarding_plan_fallback`

### Agent Query & Publish Console
- **Summary:** Allow power users to run planner-driven tool chains (rag_search, Jira, Confluence).
- **Personas:** Admin, PO, BA, Dev (self-service insights)
- **Entry Points:** `POST /agent/query`
- **Notes:** Sanitizes arguments, enforces planner policies, returns per-step artifacts.
- **Quality Coverage:** `tests/test_agent_publish.py`

### Retrieval Workbench
- **Summary:** Hybrid search across tenant knowledge (Qdrant + local fallback) with policy filtering.
- **Personas:** Admin, PO, BA, Dev
- **Entry Points:** `POST /retrieve`
- **Notes:** Unauthorized target → 403 with explicit project name; supports Rosetta narratives.
- **Quality Coverage:** `tests/test_retriever_router.py`, `tests/test_qdrant_retriever.py`, `tests/test_policy_enforcement.py`

### Knowledge Upload & Ingestion
- **Summary:** Accept documents, push to vector index, mirror locally for resilience.
- **Personas:** PO
- **Entry Points:** `POST /upload`
- **Notes:** Remote failures return 200 with fallback message; filenames preserved for UI.
- **Quality Coverage:** `tests/test_upload_routes.py`

### Skill Profile Explorer
- **Summary:** Chart developer skill vectors with recency highlights.
- **Personas:** Admin, PO, BA (any developer), Dev (self)
- **Entry Points:** `GET /skills/profile`
- **Notes:** Guards Dev role to self-only; handles `null` recency fields gracefully.
- **Quality Coverage:** `tests/test_skills_routes.py`

### Audit Log Viewer
- **Summary:** Provide auditors with recent tenant actions filtered by actor.
- **Personas:** Admin, PO, BA
- **Entry Points:** `GET /audit`
- **Notes:** Returns up to 200 rows; unauthorized tenants get 400/403 as appropriate.
- **Quality Coverage:** `tests/test_audit_routes.py`

### Integration Intake & Skill Attribution Pipeline
- **Summary:** Ingest GitHub/Jira webhooks, enforce idempotency, enrich identity, update skills.
- **Personas:** System integrations; downstream UX consumes derived data.
- **Entry Points:** `POST /events/github`, `POST /events/jira`
- **Notes:** Duplicate deliveries short-circuit; missing mappings create triage entries.
- **Quality Coverage:** `tests/test_github_webhook.py`, `tests/test_jira_webhook.py`, worker unit tests.

### Planner Tooling & Isolation Proofs
- **Summary:** Keep agent tooling safe, sanitize placeholders, emit compliance bundles.
- **Personas:** Compliance reviewers; indirectly benefits all planner-driven UX.
- **Entry Points:** Internal via planner execution; artifacts surface in API responses.
- **Notes:** Missing Atlassian config surfaces structured errors; isolation proof scripts under `artifacts/e2e`.
- **Quality Coverage:** Planner suite, `tests/test_agent_publish.py`, isolation proof smoke runs.

---

By consolidating the architecture, technical, and UX perspectives in this single README, every stakeholder—engineers, designers, product, and compliance—can quickly find the context they need while staying aligned with the autogenerated documentation pipeline.
