# Internal flow — `app.ports.onboarding.generate_plan`

- Module: `app.ports.onboarding`
- Source: [app.ports.onboarding.generate_plan](../Src/backend/app/ports/onboarding.py#L16)
- Summary: Generate an onboarding plan within tenant boundaries.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as generate_plan
    Target->>Dependency: app.application.onboarding_service.generate_onboarding
    Target->>Dependency: app.domain.schemas.OnboardingResp
    Target->>Dependency: db.get
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: user_claims.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```