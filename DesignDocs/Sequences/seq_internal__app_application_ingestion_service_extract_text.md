# Internal flow — `app.application.ingestion_service.extract_text`

- Module: `app.application.ingestion_service`
- Source: [app.application.ingestion_service.extract_text](../Src/backend/app/application/ingestion_service.py#L125)
- Summary: Decode file bytes into plain text using best-effort heuristics.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as extract_text
    Target->>Dependency: _pdf_to_text
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: file_bytes.decode
    Target->>Dependency: lower
    Target->>Dependency: name.endswith
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```