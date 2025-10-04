# Internal flow — `app.ports.planner.list_tools`

- Module: `app.ports.planner`
- Source: [app.ports.planner.list_tools](../Src/backend/app/ports/planner.py#L29)
- Summary: Return registered tool names sorted alphabetically.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as list_tools
    Target->>Dependency: _TOOL_REGISTRY.keys
    Target->>Dependency: sorted
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```