# Internal flow — `app.ports.projects.list_projects`

- Module: `app.ports.projects`
- Source: [app.ports.projects.list_projects](../Src/backend/app/ports/projects.py#L59)
- Summary: Return all projects for the provided tenant ordered by key.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as list_projects
    Target->>Dependency: _to_project_resp
    Target->>Dependency: app.domain.models.Project.key.asc
    Target->>Dependency: db.query
    Target->>Dependency: db.query.filter
    Target->>Dependency: db.query.filter.order_by
    Target->>Dependency: db.query.filter.order_by.all
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```