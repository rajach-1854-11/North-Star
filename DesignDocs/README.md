# North Star Architecture Docs

This pack is generated from source via `scripts/generate_arch_docs.py`.

## Capabilities
- FastAPI HTTP APIs for staffing, onboarding, retrieval, and audit flows.
- RQ-backed worker for GitHub/Jira ingestion and skill attribution.
- Policy enforcement, identity resolution, and agentic planner components.

## Personas
- **Platform Admin:** Configures policies, integrations, and reviews audits.
- **Project Lead:** Requests onboarding plans and checks staffing readiness.
- **Developer:** Consumes onboarding tasks and skill insights.

## Diagram Index
- [C1 – Context](C4/C1_Context.md)
- [C2 – Containers](C4/C2_Containers.md)
- [C3 – Components](C4/C3_Components.md)
- [C4 – Code](C4/C4_Code.md)
- [ERD](ERD/ERD.md)
- [Table Dictionary](ERD/ERD_Table_Dictionary.md)

## Inventory Overview
- HTTP endpoints discovered: **18**
- Background handlers: **9**
- Machine-readable graph: [inventory.json](inventory.json).

## Navigating
- Start with C1->C4 diagrams for progressively deeper architectural views.
- Use `Sequences/` for end-to-end request flows (one file per action).
- Consult the ERD for relational modeling questions and constraints.

## Backend Quickstart
1. Install deps: `pip install -e North-Star/Src/backend[dev]`.
2. Provide `.env` values (see Technical README configuration matrix).
3. Run API: `uvicorn app.main:app --reload`.
4. Run worker: `python -m worker.main` when `QUEUE_MODE=redis`.

## Glossary
- **Attribution Workflow:** Correlates PRs/issues to skill evidence.
- **Isolation Proof:** Policy proof package emitted for sensitive actions.
- **Planner/Executor:** Agentic orchestration for onboarding plan generation.
- **Retriever:** Vector search over Confluence/Jira content via Qdrant.
