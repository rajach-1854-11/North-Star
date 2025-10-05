# API POST /agent/query

- Handler: `app.routes.agent_routes.agent_query`
- Source: [app.routes.agent_routes](../Src/backend/app/routes/agent_routes.py#L18)
- Dependencies: `app.deps.require_role` via `user`
- Response model: `AgentQueryResp`

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI Router
    participant Handler as agent_query
    Client->>API: POST /agent/query
    API->>Handler: dispatch
    Handler->>Service: app.domain.schemas.AgentQueryResp
    Handler->>Service: app.ports.planner.create_plan
    Handler->>Service: app.ports.planner.execute_plan
    Handler->>Service: detail.get
    Handler->>Service: fastapi.responses.JSONResponse
    Handler->>Service: isinstance
    Handler-->>API: domain response
    API-->>Client: HTTP response
    alt Failure
        Handler-->>Client: HTTPException / 4xx
    end
```