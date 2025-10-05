# Internal flow — `app.ports.talent_graph.project_requirements`

- Module: `app.ports.talent_graph`
- Source: [app.ports.talent_graph.project_requirements](../Src/backend/app/ports/talent_graph.py#L78)
- Summary: Returns a dict of required skills (path_cache -> importance weight).

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as project_requirements
    Target->>Dependency: db.execute
    Target->>Dependency: db.execute.all
    Target->>Dependency: float
    Target->>Dependency: sqlalchemy.text
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```