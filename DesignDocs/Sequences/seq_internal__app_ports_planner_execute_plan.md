# Internal flow — `app.ports.planner.execute_plan`

- Module: `app.ports.planner`
- Source: [app.ports.planner.execute_plan](../Src/backend/app/ports/planner.py#L520)
- Summary: Execute a plan against registered tools while enforcing RBAC.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as execute_plan
    Target->>Dependency: _resolve_value
    Target->>Dependency: _sanitize_tool_args
    Target->>Dependency: app.application.policy_bus.enforce
    Target->>Dependency: enumerate
    Target->>Dependency: isinstance
    Target->>Dependency: loguru.logger.exception
    Target->>Dependency: loguru.logger.warning
    Target->>Dependency: plan.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```