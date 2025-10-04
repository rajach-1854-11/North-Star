# Worker flow — `worker.handlers.skill_extractor.apply_skill_delta`

- Module: `worker.handlers.skill_extractor`
- Source: [worker.handlers.skill_extractor.apply_skill_delta](../Src/backend/worker/handlers/skill_extractor.py#L77)
- Summary: Apply a score delta to a developer skill, ensuring timestamps update.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as apply_skill_delta
    Target->>Dependency: session.execute
    Target->>Dependency: sqlalchemy.text
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```