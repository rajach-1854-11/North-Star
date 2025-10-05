# Internal flow — `app.ports.assignments.list_assignments_for_project`

- Module: `app.ports.assignments`
- Source: [app.ports.assignments.list_assignments_for_project](../Src/backend/app/ports/assignments.py#L94)
- Summary: List assignments for the supplied project within the tenant.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as list_assignments_for_project
    Target->>Dependency: _ensure_same_tenant
    Target->>Dependency: _to_assignment_resp
    Target->>Dependency: app.domain.models.Assignment.id.asc
    Target->>Dependency: app.domain.schemas.AssignmentListResp
    Target->>Dependency: db.get
    Target->>Dependency: db.query
    Target->>Dependency: db.query.join
    Target->>Dependency: db.query.join.filter
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```