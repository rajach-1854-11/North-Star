# Internal flow — `app.application.talent_service._utc_now`

- Module: `app.application.talent_service`
- Source: [app.application.talent_service._utc_now](../Src/backend/app/application/talent_service.py#L14)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _utc_now
    Target->>Dependency: datetime.datetime.now
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```