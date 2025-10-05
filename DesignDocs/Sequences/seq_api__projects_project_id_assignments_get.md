# API GET /projects/{project_id}/assignments

- Handler: `app.routes.assignment_routes.get_project_assignments`
- Source: [app.routes.assignment_routes](../Src/backend/app/routes/assignment_routes.py#L66)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin, PO, BA)
- Response model: `AssignmentListResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as get_project_assignments
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: GET /projects/{project_id}/assignments
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.assignments.list_assignments_for_project
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```