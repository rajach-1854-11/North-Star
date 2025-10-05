# Internal flow — `app.application.staffing_service._ensure_aware`

- Module: `app.application.staffing_service`
- Source: [app.application.staffing_service._ensure_aware](../Src/backend/app/application/staffing_service.py#L32)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _ensure_aware
    Target->>Dependency: timestamp.replace
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```