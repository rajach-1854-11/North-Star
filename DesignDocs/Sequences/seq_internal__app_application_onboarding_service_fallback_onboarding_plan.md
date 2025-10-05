# Internal flow — `app.application.onboarding_service._fallback_onboarding_plan`

- Module: `app.application.onboarding_service`
- Source: [app.application.onboarding_service._fallback_onboarding_plan](../Src/backend/app/application/onboarding_service.py#L80)
- Summary: Produce a deterministic onboarding plan when the planner is unavailable.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _fallback_onboarding_plan
    Target->>Dependency: app.domain.schemas.OnboardingPlan
    Target->>Dependency: max
    Target->>Dependency: min
    Target->>Dependency: tasks.append
    Target->>Dependency: tasks.extend
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```