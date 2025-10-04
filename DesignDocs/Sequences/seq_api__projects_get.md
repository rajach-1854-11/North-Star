# API GET /projects

- Handler: `app.routes.project_read_routes.list_tenant_projects`
- Source: [app.routes.project_read_routes](../Src/backend/app/routes/project_read_routes.py#L18)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin, PO, BA, Dev)
- Response model: `List[ProjectResp]`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as list_tenant_projects
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: GET /projects
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.projects.list_projects
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```