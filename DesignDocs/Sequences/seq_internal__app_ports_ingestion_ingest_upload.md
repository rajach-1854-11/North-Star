# Internal flow — `app.ports.ingestion.ingest_upload`

- Module: `app.ports.ingestion`
- Source: [app.ports.ingestion.ingest_upload](../Src/backend/app/ports/ingestion.py#L16)
- Summary: Ingest a document for the caller's tenant and return upload stats.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as ingest_upload
    Target->>Dependency: app.application.ingestion_service.extract_text
    Target->>Dependency: app.application.ingestion_service.ingest_file
    Target->>Dependency: app.application.local_kb.store_chunks
    Target->>Dependency: app.domain.schemas.UploadResp
    Target->>Dependency: db.query
    Target->>Dependency: db.query.filter
    Target->>Dependency: db.query.filter.one_or_none
    Target->>Dependency: fastapi.HTTPException
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```