# Worker flow — `worker.handlers.skill_extractor.ensure_skill`

- Module: `worker.handlers.skill_extractor`
- Source: [worker.handlers.skill_extractor.ensure_skill](../Src/backend/worker/handlers/skill_extractor.py#L51)
- Summary: Ensure a skill hierarchy path exists and return the leaf skill id.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as ensure_skill
    Target->>Dependency: int
    Target->>Dependency: join
    Target->>Dependency: len
    Target->>Dependency: session.execute
    Target->>Dependency: session.execute.scalar_one
    Target->>Dependency: sqlalchemy.text
    Target->>Dependency: str
    Target->>Dependency: str.strip
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```