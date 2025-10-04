# API POST /auth/token

- Handler: `app.routes.auth_routes.token`
- Source: [app.routes.auth_routes](../Src/backend/app/routes/auth_routes.py#L22)
- Dependencies: `app.deps.get_db` via `db`
- Response model: `TokenResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as token
    participant DB as Database
    Client->>API: POST /auth/token
    API->>Handler: dispatch
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: accessible.update
    Handler->>Service: app.domain.models.Assignment.status.is_
    Handler->>Service: app.domain.schemas.TokenResp
    Handler->>Service: db.query
    Handler->>Service: db.query.filter
    Handler->>Service: db.query.filter.all
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```