# Internal flow — `app.application.contrastive_mapper.ABMapper._get_session`

- Module: `app.application.contrastive_mapper`
- Source: [app.application.contrastive_mapper.ABMapper._get_session](../Src/backend/app/application/contrastive_mapper.py#L72)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _get_session
    Target->>Dependency: RuntimeError
    Target->>Dependency: self._session_factory
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```