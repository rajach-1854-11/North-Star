# API PATCH /admin/users/{user_id}/role

- Handler: `app.routes.admin_user_routes.patch_user_role`
- Source: [app.routes.admin_user_routes](../Src/backend/app/routes/admin_user_routes.py#L29)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin)
- Response model: `UserResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as patch_user_role
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: PATCH /admin/users/{user_id}/role
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.users.update_user_role
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```