# Internal flow — `app.ports.users.list_users`

- Module: `app.ports.users`
- Source: [app.ports.users.list_users](../Src/backend/app/ports/users.py#L20)
- Summary: Return all users for the given tenant ordered by username.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as list_users
    Target->>Dependency: _to_user_resp
    Target->>Dependency: app.domain.models.User.username.asc
    Target->>Dependency: app.domain.schemas.UserListResp
    Target->>Dependency: db.query
    Target->>Dependency: db.query.filter
    Target->>Dependency: db.query.filter.order_by
    Target->>Dependency: db.query.filter.order_by.all
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```