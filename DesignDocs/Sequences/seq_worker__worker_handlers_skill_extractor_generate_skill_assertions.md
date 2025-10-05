# Worker flow — `worker.handlers.skill_extractor.generate_skill_assertions`

- Module: `worker.handlers.skill_extractor`
- Source: [worker.handlers.skill_extractor.generate_skill_assertions](../Src/backend/worker/handlers/skill_extractor.py#L30)
- Summary: Call the planner to derive skill assertions without mutating the database.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as generate_skill_assertions
    Target->>Dependency: _format_prompt
    Target->>External: app.adapters.cerebras_planner.chat_json
    Target->>Dependency: assertions.append
    Target->>Dependency: float
    Target->>Dependency: output.get
    Target->>Dependency: raw.get
    Target->>Dependency: str
    Target->>Dependency: str.strip
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```