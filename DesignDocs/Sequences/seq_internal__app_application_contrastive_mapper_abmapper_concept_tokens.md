# Internal flow — `app.application.contrastive_mapper.ABMapper._concept_tokens`

- Module: `app.application.contrastive_mapper`
- Source: [app.application.contrastive_mapper.ABMapper._concept_tokens](../Src/backend/app/application/contrastive_mapper.py#L80)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _concept_tokens
    Target->>Dependency: cls._TOKEN_RE.findall
    Target->>Dependency: len
    Target->>Dependency: t.lower
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```