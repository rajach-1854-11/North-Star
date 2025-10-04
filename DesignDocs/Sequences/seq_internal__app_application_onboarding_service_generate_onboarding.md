# Internal flow — `app.application.onboarding_service.generate_onboarding`

- Module: `app.application.onboarding_service`
- Source: [app.application.onboarding_service.generate_onboarding](../Src/backend/app/application/onboarding_service.py#L20)
- Summary: Create an onboarding plan by merging planner output with graph-derived gaps.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as generate_onboarding
    Target->>Dependency: _fallback_onboarding_plan
    Target->>Dependency: _format_gap_bullets
    Target->>Dependency: _planner.create_plan
    Target->>Dependency: _planner.execute_plan
    Target->>Dependency: app.domain.schemas.OnboardingPlan
    Target->>Dependency: app.ports.talent_graph.project_skill_gap
    Target->>Dependency: artifacts.get
    Target->>Dependency: exec_res.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```