# Worker flow — `worker.handlers.skill_extractor._format_prompt`

- Module: `worker.handlers.skill_extractor`
- Source: [worker.handlers.skill_extractor._format_prompt](../Src/backend/worker/handlers/skill_extractor.py#L21)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as _format_prompt
    Target->>Dependency: join
    Target->>Dependency: payload.keys
    Target->>Dependency: sorted
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```