# Internal flow — `app.ports.audit.list_audit_entries`

- Module: `app.ports.audit`
- Source: [app.ports.audit.list_audit_entries](../Src/backend/app/ports/audit.py#L14)
- Summary: Return recent audit entries for the caller's tenant.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as list_audit_entries
    Target->>Dependency: app.domain.models.AuditLog.ts.desc
    Target->>Dependency: app.domain.schemas.AuditEntry
    Target->>Dependency: app.domain.schemas.AuditResp
    Target->>Dependency: db.query
    Target->>Dependency: db.query.filter
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: max
    Target->>Dependency: min
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```