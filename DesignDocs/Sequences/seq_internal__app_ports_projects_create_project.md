# Internal flow — `app.ports.projects.create_project`

- Module: `app.ports.projects`
- Source: [app.ports.projects.create_project](../Src/backend/app/ports/projects.py#L24)
- Summary: Create a new project scoped to *tenant_id* and return its schema.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as create_project
    Target->>Dependency: _to_project_resp
    Target->>Dependency: app.domain.models.Project
    Target->>Dependency: db.add
    Target->>Dependency: db.commit
    Target->>Dependency: db.refresh
    Target->>Dependency: db.rollback
    Target->>Dependency: fastapi.HTTPException
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```