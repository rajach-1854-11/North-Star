# Internal flow — `app.ports.assignments.update_assignment`

- Module: `app.ports.assignments`
- Source: [app.ports.assignments.update_assignment](../Src/backend/app/ports/assignments.py#L63)
- Summary: Update fields on an assignment while enforcing tenant boundaries.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as update_assignment
    Target->>Dependency: _ensure_same_tenant
    Target->>Dependency: _to_assignment_resp
    Target->>Dependency: db.commit
    Target->>Dependency: db.get
    Target->>Dependency: db.refresh
    Target->>Dependency: fastapi.HTTPException
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```