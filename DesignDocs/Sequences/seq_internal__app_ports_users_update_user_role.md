# Internal flow — `app.ports.users.update_user_role`

- Module: `app.ports.users`
- Source: [app.ports.users.update_user_role](../Src/backend/app/ports/users.py#L29)
- Summary: Update the role for a user within the same tenant.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as update_user_role
    Target->>Dependency: _to_user_resp
    Target->>Dependency: db.commit
    Target->>Dependency: db.get
    Target->>Dependency: db.refresh
    Target->>Dependency: fastapi.HTTPException
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```