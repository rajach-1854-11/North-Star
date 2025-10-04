# Internal flow — `app.ports.planner._fallback_plan`

- Module: `app.ports.planner`
- Source: [app.ports.planner._fallback_plan](../Src/backend/app/ports/planner.py#L93)
- Summary: Generate a deterministic plan when the planner service is unavailable.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _fallback_plan
    Target->>Dependency: join
    Target->>Dependency: task_prompt.strip
    Target->>Dependency: task_prompt.strip.splitlines
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```