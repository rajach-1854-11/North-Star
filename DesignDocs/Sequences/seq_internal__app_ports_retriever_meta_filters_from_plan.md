# Internal flow — `app.ports.retriever._meta_filters_from_plan`

- Module: `app.ports.retriever`
- Source: [app.ports.retriever._meta_filters_from_plan](../Src/backend/app/ports/retriever.py#L63)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _meta_filters_from_plan
    Target->>Dependency: dict
    Target->>Dependency: node.args.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```