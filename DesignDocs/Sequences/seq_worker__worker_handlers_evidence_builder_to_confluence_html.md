# Worker flow — `worker.handlers.evidence_builder.to_confluence_html`

- Module: `worker.handlers.evidence_builder`
- Source: [worker.handlers.evidence_builder.to_confluence_html](../Src/backend/worker/handlers/evidence_builder.py#L51)
- Summary: Convert raw evidence text into basic Confluence storage HTML.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as to_confluence_html
    Target->>Dependency: esc.split
    Target->>Dependency: evidence.replace
    Target->>Dependency: evidence.replace.replace
    Target->>Dependency: evidence.replace.replace.replace
    Target->>Dependency: join
    Target->>Dependency: ln.strip
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```