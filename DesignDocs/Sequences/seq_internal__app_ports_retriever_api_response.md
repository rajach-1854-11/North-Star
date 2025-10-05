# Internal flow — `app.ports.retriever.api_response`

- Module: `app.ports.retriever`
- Source: [app.ports.retriever.api_response](../Src/backend/app/ports/retriever.py#L229)
- Summary: Coerce internal payload structure into the API response schema.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as api_response
    Target->>Dependency: app.domain.schemas.RetrieveResp
    Target->>Dependency: payload.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```