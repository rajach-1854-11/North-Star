# Internal flow — `app.application.retrieval_service.retrieve_context`

- Module: `app.application.retrieval_service`
- Source: [app.application.retrieval_service.retrieve_context](../Src/backend/app/application/retrieval_service.py#L11)
- Summary: Run the configured retriever and normalise its response.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as retrieve_context
    Target->>Dependency: app.ports.retriever.api_response
    Target->>Dependency: app.ports.retriever.rag_search
    Target->>Dependency: list
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```