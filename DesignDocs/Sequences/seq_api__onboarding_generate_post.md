# API POST /onboarding/generate

- Handler: `app.routes.onboarding_routes.generate`
- Source: [app.routes.onboarding_routes](../Src/backend/app/routes/onboarding_routes.py#L18)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin, PO)
- Response model: `OnboardingResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as generate
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: POST /onboarding/generate
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.onboarding.generate_plan
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```