# Internal flow — `app.ports.planner.register_tool`

- Module: `app.ports.planner`
- Source: [app.ports.planner.register_tool](../Src/backend/app/ports/planner.py#L24)
- Summary: Register a callable for planner execution under *name*.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as register_tool
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```