# Internal flow — `app.ports.planner._adf_from_text`

- Module: `app.ports.planner`
- Source: [app.ports.planner._adf_from_text](../Src/backend/app/ports/planner.py#L196)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _adf_from_text
    Target->>Dependency: strip
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```