# Worker flow — `worker.handlers.evidence_builder.to_jira_description`

- Module: `worker.handlers.evidence_builder`
- Source: [worker.handlers.evidence_builder.to_jira_description](../Src/backend/worker/handlers/evidence_builder.py#L63)
- Summary: Convert evidence text into Jira's Atlassian Document Format.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as to_jira_description
    Target->>Dependency: blocks.append
    Target->>Dependency: evidence.split
    Target->>Dependency: line.strip
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```