# API POST /retrieve

- Handler: `app.routes.retrieve_routes.retrieve`
- Source: [app.routes.retrieve_routes](../Src/backend/app/routes/retrieve_routes.py#L10)
- Dependencies: `app.deps.require_role` via `user` (roles: Admin, PO, BA, Dev)
- Response model: `RetrieveResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as retrieve
    participant Policy as Policy Check
    Client->>API: POST /retrieve
    API->>Handler: dispatch
    Handler->>Policy: require_role
    Policy-->>Handler: authorize
    Handler->>Service: app.ports.retriever.api_response
    Handler->>Service: app.ports.retriever.rag_search
    Handler->>Service: fastapi.HTTPException
    Handler->>Service: user.get
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```