# Internal flow — `app.ports.retriever._dedupe_by_chunk_id`

- Module: `app.ports.retriever`
- Source: [app.ports.retriever._dedupe_by_chunk_id](../Src/backend/app/ports/retriever.py#L30)
- Summary: Merge duplicate chunks across collections preferring the best score.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _dedupe_by_chunk_id
    Target->>Dependency: add
    Target->>Dependency: app.utils.hashing.hash_text
    Target->>Dependency: best.items
    Target->>Dependency: dict
    Target->>Dependency: join
    Target->>Dependency: merged.append
    Target->>Dependency: merged.sort
    Target->>Dependency: pl.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```