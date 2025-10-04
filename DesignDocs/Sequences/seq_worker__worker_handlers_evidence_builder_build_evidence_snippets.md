# Worker flow — `worker.handlers.evidence_builder.build_evidence_snippets`

- Module: `worker.handlers.evidence_builder`
- Source: [worker.handlers.evidence_builder.build_evidence_snippets](../Src/backend/worker/handlers/evidence_builder.py#L6)
- Summary: Build a compact, LLM-friendly evidence string:

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as build_evidence_snippets
    Target->>Dependency: buf.append
    Target->>Dependency: join
    Target->>Dependency: len
    Target->>Dependency: per_source.get
    Target->>Dependency: seen_ids.add
    Target->>Dependency: set
    Target->>Dependency: split
    Target->>Dependency: str
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```