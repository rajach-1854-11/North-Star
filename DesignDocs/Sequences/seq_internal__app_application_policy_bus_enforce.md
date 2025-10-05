# Internal flow — `app.application.policy_bus.enforce`

- Module: `app.application.policy_bus`
- Source: [app.application.policy_bus.enforce](../Src/backend/app/application/policy_bus.py#L44)
- Summary: Ensure *role* can execute *tool*; raise ``HTTPException`` otherwise.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as enforce
    Target->>Dependency: ALLOWED_TOOLS.get
    Target->>Dependency: fastapi.HTTPException
    Target->>Dependency: set
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```