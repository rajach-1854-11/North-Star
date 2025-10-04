# Internal flow — `app.ports.assignments.create_assignment`

- Module: `app.ports.assignments`
- Source: [app.ports.assignments.create_assignment](../Src/backend/app/ports/assignments.py#L32)
- Summary: Create a new assignment ensuring tenant coherence.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as create_assignment
    Target->>Dependency: _ensure_same_tenant
    Target->>Dependency: _to_assignment_resp
    Target->>Dependency: app.domain.models.Assignment
    Target->>Dependency: db.add
    Target->>Dependency: db.commit
    Target->>Dependency: db.get
    Target->>Dependency: db.refresh
    Target->>Dependency: db.rollback
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```