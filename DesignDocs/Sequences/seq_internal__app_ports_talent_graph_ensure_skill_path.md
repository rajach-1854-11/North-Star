# Internal flow — `app.ports.talent_graph.ensure_skill_path`

- Module: `app.ports.talent_graph`
- Source: [app.ports.talent_graph.ensure_skill_path](../Src/backend/app/ports/talent_graph.py#L27)
- Summary: Ensure a hierarchical path exists in 'skill' table. Returns leaf skill_id.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as ensure_skill_path
    Target->>Dependency: ValueError
    Target->>Dependency: db.execute
    Target->>Dependency: db.execute.scalar
    Target->>Dependency: join
    Target->>Dependency: len
    Target->>Dependency: sqlalchemy.select
    Target->>Dependency: sqlalchemy.select.where
    Target->>Dependency: sqlalchemy.text
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```