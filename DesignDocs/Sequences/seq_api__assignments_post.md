# API POST /assignments

- Handler: `app.routes.assignment_routes.post_assignment`
- Source: [app.routes.assignment_routes](../Src/backend/app/routes/assignment_routes.py#L27)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin, PO)
- Response model: `AssignmentResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as post_assignment
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: POST /assignments
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.assignments.create_assignment
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```