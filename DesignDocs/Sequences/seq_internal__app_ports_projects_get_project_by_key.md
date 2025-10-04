# Internal flow — `app.ports.projects.get_project_by_key`

- Module: `app.ports.projects`
- Source: [app.ports.projects.get_project_by_key](../Src/backend/app/ports/projects.py#L46)
- Summary: Return a single project by key within the caller's tenant.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as get_project_by_key
    Target->>Dependency: _to_project_resp
    Target->>Dependency: db.query
    Target->>Dependency: db.query.filter
    Target->>Dependency: db.query.filter.one_or_none
    Target->>Dependency: fastapi.HTTPException
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```