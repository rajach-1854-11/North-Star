# Internal flow — `app.application.contrastive_mapper.ABMapper.__init__`

- Module: `app.application.contrastive_mapper`
- Source: [app.application.contrastive_mapper.ABMapper.__init__](../Src/backend/app/application/contrastive_mapper.py#L61)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as __init__
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```