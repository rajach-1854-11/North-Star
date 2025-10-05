# Internal flow — `app.ports.talent_graph.rollup_developer_scores`

- Module: `app.ports.talent_graph`
- Source: [app.ports.talent_graph.rollup_developer_scores](../Src/backend/app/ports/talent_graph.py#L58)
- Summary: Collapses developer_skill rows into a dict keyed by path_cache with max score.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as rollup_developer_scores
    Target->>Dependency: collections.defaultdict
    Target->>Dependency: db.execute
    Target->>Dependency: db.execute.all
    Target->>Dependency: dict
    Target->>Dependency: float
    Target->>Dependency: max
    Target->>Dependency: sqlalchemy.text
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```