# Internal flow — `app.application.ingestion_service._pdf_to_text`

- Module: `app.application.ingestion_service`
- Source: [app.application.ingestion_service._pdf_to_text](../Src/backend/app/application/ingestion_service.py#L107)
- Summary: Extract text from a PDF file.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _pdf_to_text
    Target->>Dependency: PdfReader
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: io.BytesIO
    Target->>Dependency: join
    Target->>Dependency: join.strip
    Target->>Dependency: loguru.logger.warning
    Target->>Dependency: page.extract_text
    Target->>Dependency: pages.append
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```