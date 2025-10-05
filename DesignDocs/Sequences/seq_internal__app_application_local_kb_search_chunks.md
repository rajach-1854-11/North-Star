# Internal flow — `app.application.local_kb.search_chunks`

- Module: `app.application.local_kb`
- Source: [app.application.local_kb.search_chunks](../Src/backend/app/application/local_kb.py#L90)
- Summary: Retrieve chunks via simple keyword scoring for fallback responses.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as search_chunks
    Target->>Dependency: _tokenise
    Target->>Dependency: chunk_tokens.count
    Target->>Dependency: db.execute
    Target->>Dependency: db.execute.scalars
    Target->>Dependency: db.execute.scalars.all
    Target->>Dependency: evt.payload_json.get
    Target->>Dependency: get
    Target->>Dependency: math.log
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```