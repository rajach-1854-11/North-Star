# Internal flow — `app.ports.talent_graph.compute_skill_gaps`

- Module: `app.ports.talent_graph`
- Source: [app.ports.talent_graph.compute_skill_gaps](../Src/backend/app/ports/talent_graph.py#L95)
- Summary: For each required skill, compute gap = max(0, required - current).

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as compute_skill_gaps
    Target->>Dependency: dev_vec.get
    Target->>Dependency: float
    Target->>Dependency: gaps.append
    Target->>Dependency: gaps.sort
    Target->>Dependency: max
    Target->>Dependency: req_vec.items
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```