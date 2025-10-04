# API GET /audit

- Handler: `app.routes.audit_routes.audit`
- Source: [app.routes.audit_routes](../Src/backend/app/routes/audit_routes.py#L18)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `_user` (roles: Admin, PO, BA)
- Response model: `AuditResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as audit
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: GET /audit
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.audit.list_audit_entries
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```