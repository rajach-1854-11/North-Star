# Internal flow — `app.ports.planner._default_confluence_body`

- Module: `app.ports.planner`
- Source: [app.ports.planner._default_confluence_body](../Src/backend/app/ports/planner.py#L135)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _default_confluence_body
    Target->>Dependency: gap.get
    Target->>Dependency: gap_items.append
    Target->>Dependency: int
    Target->>Dependency: isinstance
    Target->>Dependency: join
    Target->>Dependency: output.get
    Target->>Dependency: plan.get
    Target->>Dependency: str
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```