# Internal flow — `app.application.ingestion_service.ingest_text`

- Module: `app.application.ingestion_service`
- Source: [app.application.ingestion_service.ingest_text](../Src/backend/app/application/ingestion_service.py#L59)
- Summary: Chunk, embed, and upsert plain text into Qdrant.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as ingest_text
    Target->>Dependency: _collection_name
    Target->>Dependency: _to_points
    Target->>External: app.adapters.dense_bge.embed_batch
    Target->>External: app.adapters.qdrant_client.ensure_collection
    Target->>External: app.adapters.qdrant_client.upsert_points
    Target->>Dependency: app.domain.errors.ExternalServiceError
    Target->>Dependency: app.utils.chunk.smart_chunks
    Target->>Dependency: fastapi.HTTPException
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```