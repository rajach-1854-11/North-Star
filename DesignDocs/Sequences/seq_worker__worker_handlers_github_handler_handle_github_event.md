# Worker flow — `worker.handlers.github_handler.handle_github_event`

- Module: `worker.handlers.github_handler`
- Source: [worker.handlers.github_handler.handle_github_event](../Src/backend/worker/handlers/github_handler.py#L13)
- Summary: Dispatch a GitHub webhook payload to the GitHub processor.

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as handle_github_event
    Target->>Dependency: logger.info
    Target->>Dependency: processor.body.get
    Target->>Dependency: processor.body.get.get
    Target->>Dependency: processor.process
    Target->>Dependency: worker.services.github_processor.GitHubEventProcessor
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```