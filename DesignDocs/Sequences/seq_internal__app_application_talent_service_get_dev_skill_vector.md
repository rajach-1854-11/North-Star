# Internal flow — `app.application.talent_service.get_dev_skill_vector`

- Module: `app.application.talent_service`
- Source: [app.application.talent_service.get_dev_skill_vector](../Src/backend/app/application/talent_service.py#L27)
- Summary: Return a mapping of skill path to score for a developer.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as get_dev_skill_vector
    Target->>Dependency: db.query
    Target->>Dependency: db.query.join
    Target->>Dependency: db.query.join.filter
    Target->>Dependency: db.query.join.filter.all
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```