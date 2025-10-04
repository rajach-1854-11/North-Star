# Internal flow — `app.application.staffing_service.cosine_dict`

- Module: `app.application.staffing_service`
- Source: [app.application.staffing_service.cosine_dict](../Src/backend/app/application/staffing_service.py#L17)
- Summary: Compute cosine similarity between two sparse vectors represented as dicts.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as cosine_dict
    Target->>Dependency: lhs.values
    Target->>Dependency: math.sqrt
    Target->>Dependency: rhs.values
    Target->>Dependency: set
    Target->>Dependency: set.intersection
    Target->>Dependency: sum
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```