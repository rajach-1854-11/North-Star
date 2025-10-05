# API GET /projects/{key}

- Handler: `app.routes.project_read_routes.get_project`
- Source: [app.routes.project_read_routes](../Src/backend/app/routes/project_read_routes.py#L29)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin, PO, BA, Dev)
- Response model: `ProjectResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as get_project
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: GET /projects/{key}
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.projects.get_project_by_key
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```