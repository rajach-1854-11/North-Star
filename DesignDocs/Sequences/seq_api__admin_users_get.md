# API GET /admin/users

- Handler: `app.routes.admin_user_routes.list_tenant_users`
- Source: [app.routes.admin_user_routes](../Src/backend/app/routes/admin_user_routes.py#L18)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin)
- Response model: `UserListResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as list_tenant_users
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: GET /admin/users
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.users.list_users
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```