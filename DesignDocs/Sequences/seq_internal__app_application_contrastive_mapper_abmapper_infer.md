# Internal flow — `app.application.contrastive_mapper.ABMapper.infer`

- Module: `app.application.contrastive_mapper`
- Source: [app.application.contrastive_mapper.ABMapper.infer](../Src/backend/app/application/contrastive_mapper.py#L128)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as infer
    Target->>Dependency: MapperOut
    Target->>Dependency: abs
    Target->>Dependency: agg.get
    Target->>Dependency: agg.items
    Target->>Dependency: app.domain.models.ABMapEdge
    Target->>Dependency: app.utils.hashing.hash_text
    Target->>Dependency: curated.append
    Target->>Dependency: float
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```