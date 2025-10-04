# Internal flow — `app.ports.planner._resolve_value`

- Module: `app.ports.planner`
- Source: [app.ports.planner._resolve_value](../Src/backend/app/ports/planner.py#L229)
- Summary: Recursively resolve templated placeholders from the execution context.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _resolve_value
    Target->>Dependency: _PLACEHOLDER.sub
    Target->>Dependency: _resolve_value
    Target->>Dependency: isinstance
    Target->>Dependency: match.group
    Target->>Dependency: path.split
    Target->>Dependency: str
    Target->>Dependency: value.items
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```