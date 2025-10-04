# Internal flow — `app.application.talent_service.get_project_required_skills`

- Module: `app.application.talent_service`
- Source: [app.application.talent_service.get_project_required_skills](../Src/backend/app/application/talent_service.py#L39)
- Summary: Return required skills for a project keyed by skill path.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as get_project_required_skills
    Target->>Dependency: db.query
    Target->>Dependency: db.query.join
    Target->>Dependency: db.query.join.filter
    Target->>Dependency: db.query.join.filter.all
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```