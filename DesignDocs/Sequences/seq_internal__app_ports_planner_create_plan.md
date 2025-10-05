# Internal flow — `app.ports.planner.create_plan`

- Module: `app.ports.planner`
- Source: [app.ports.planner.create_plan](../Src/backend/app/ports/planner.py#L55)
- Summary: Call the planner LLM and return the generated plan payload.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as create_plan
    Target->>Dependency: _fallback_plan
    Target->>Dependency: chat_impl
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: format
    Target->>Dependency: isinstance
    Target->>Dependency: join
    Target->>Dependency: loguru.logger.exception
    Target->>Dependency: loguru.logger.warning
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```