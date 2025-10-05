# Internal flow — `app.application.contrastive_mapper.ABMapper.fit`

- Module: `app.application.contrastive_mapper`
- Source: [app.application.contrastive_mapper.ABMapper.fit](../Src/backend/app/application/contrastive_mapper.py#L84)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as fit
    Target->>Dependency: aggregate.get
    Target->>Dependency: app.domain.models.TenantMapperWeights
    Target->>Dependency: float
    Target->>Dependency: left.get
    Target->>Dependency: len
    Target->>Dependency: loguru.logger.info
    Target->>Dependency: map
    Target->>Dependency: right.get
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```