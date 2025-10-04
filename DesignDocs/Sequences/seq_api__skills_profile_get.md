# API GET /skills/profile

- Handler: `app.routes.skills_routes.profile`
- Source: [app.routes.skills_routes](../Src/backend/app/routes/skills_routes.py#L18)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.get_current_user` via `_user`
- Response model: `SkillProfileResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as profile
    participant DB as Database
    Client->>API: GET /skills/profile
    API->>Handler: dispatch
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.skills.developer_profile
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```