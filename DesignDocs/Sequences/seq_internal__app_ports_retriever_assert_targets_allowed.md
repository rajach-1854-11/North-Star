# Internal flow — `app.ports.retriever._assert_targets_allowed`

- Module: `app.ports.retriever`
- Source: [app.ports.retriever._assert_targets_allowed](../Src/backend/app/ports/retriever.py#L23)
- Summary: Ensure requested targets are within the caller's accessible projects.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _assert_targets_allowed
    Target->>Dependency: fastapi.HTTPException
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```