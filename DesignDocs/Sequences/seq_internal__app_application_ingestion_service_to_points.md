# Internal flow — `app.application.ingestion_service._to_points`

- Module: `app.application.ingestion_service`
- Source: [app.application.ingestion_service._to_points](../Src/backend/app/application/ingestion_service.py#L28)
- Summary: Convert embedded chunks into components suitable for upsert.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _to_points
    Target->>External: app.adapters.sparse_hash.encode_sparse
    Target->>Dependency: app.utils.hashing.hash_text
    Target->>Dependency: enumerate
    Target->>Dependency: ids.append
    Target->>Dependency: payloads.append
    Target->>External: qdrant_client.http.models.SparseVector
    Target->>Dependency: sparse_vectors.append
    Target->>Dependency: str
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```