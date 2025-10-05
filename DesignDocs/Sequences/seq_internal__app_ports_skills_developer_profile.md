# Internal flow — `app.ports.skills.developer_profile`

- Module: `app.ports.skills`
- Source: [app.ports.skills.developer_profile](../Src/backend/app/ports/skills.py#L15)
- Summary: Return the developer skill profile within tenant boundaries.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as developer_profile
    Target->>Dependency: app.domain.models.DeveloperSkill.score.desc
    Target->>Dependency: app.domain.schemas.SkillEntry
    Target->>Dependency: app.domain.schemas.SkillProfileResp
    Target->>Dependency: db.execute
    Target->>Dependency: db.execute.all
    Target->>Dependency: db.get
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: float
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```