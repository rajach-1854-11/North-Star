# Internal flow — `app.ports.staffing.recommend_staff`

- Module: `app.ports.staffing`
- Source: [app.ports.staffing.recommend_staff](../Src/backend/app/ports/staffing.py#L15)
- Summary: Return staffing recommendations ensuring tenant access and schema conversion.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as recommend_staff
    Target->>Dependency: app.application.staffing_service.rank_candidates
    Target->>Dependency: app.domain.schemas.StaffCandidate
    Target->>Dependency: app.domain.schemas.StaffResp
    Target->>Dependency: db.get
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: user_claims.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```