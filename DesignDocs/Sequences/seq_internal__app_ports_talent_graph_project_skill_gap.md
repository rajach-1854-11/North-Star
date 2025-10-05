# Internal flow — `app.ports.talent_graph.project_skill_gap`

- Module: `app.ports.talent_graph`
- Source: [app.ports.talent_graph.project_skill_gap](../Src/backend/app/ports/talent_graph.py#L109)
- Summary: Convenience wrapper: compute gaps for a developer against a project's required skills.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as project_skill_gap
    Target->>Dependency: compute_skill_gaps
    Target->>Dependency: project_requirements
    Target->>Dependency: rollup_developer_scores
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```