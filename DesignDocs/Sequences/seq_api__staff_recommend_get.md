# API GET /staff/recommend

- Handler: `app.routes.staff_routes.recommend`
- Source: [app.routes.staff_routes](../Src/backend/app/routes/staff_routes.py#L18)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin, PO, BA)
- Response model: `StaffResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as recommend
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: GET /staff/recommend
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.staffing.recommend_staff
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```