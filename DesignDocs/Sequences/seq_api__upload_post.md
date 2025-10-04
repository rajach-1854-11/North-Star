# API POST /upload

- Handler: `app.routes.upload_routes.upload`
- Source: [app.routes.upload_routes](../Src/backend/app/routes/upload_routes.py#L18)
- Dependencies: `app.deps.get_db` via `db`, `app.deps.require_role` via `user` (roles: Admin, PO)
- Response model: `UploadResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as upload
    participant Policy as Policy Check
    participant DB as Database
    Client->>API: POST /upload
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>DB: use Session
    DB-->>Handler: result set
    Handler->>Service: app.ports.ingestion.ingest_upload
    Handler->>Service: file.read
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```