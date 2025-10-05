# Internal flow — `app.application.local_kb.store_chunks`

- Module: `app.application.local_kb`
- Source: [app.application.local_kb.store_chunks](../Src/backend/app/application/local_kb.py#L24)
- Summary: Persist document chunks into the ``event`` table for fallback retrieval.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as store_chunks
    Target->>Dependency: ValueError
    Target->>Dependency: app.domain.models.Event
    Target->>Dependency: app.utils.chunk.smart_chunks
    Target->>Dependency: app.utils.hashing.hash_text
    Target->>Dependency: db.add_all
    Target->>Dependency: db.commit
    Target->>Dependency: db.delete
    Target->>Dependency: db.query
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```