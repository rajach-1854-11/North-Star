# Internal flow — `app.application.staffing_service.rank_candidates`

- Module: `app.application.staffing_service`
- Source: [app.application.staffing_service.rank_candidates](../Src/backend/app/application/staffing_service.py#L38)
- Summary: Return ranked candidate dictionaries for the requested project.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as rank_candidates
    Target->>Dependency: _ensure_aware
    Target->>Dependency: app.application.talent_service.get_dev_skill_vector
    Target->>Dependency: app.application.talent_service.get_project_required_skills
    Target->>Dependency: app.application.talent_service.recency_boost
    Target->>Dependency: app.domain.models.Skill.path_cache.in_
    Target->>Dependency: app.ports.talent_graph.project_skill_gap
    Target->>Dependency: cosine_dict
    Target->>Dependency: db.execute
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```