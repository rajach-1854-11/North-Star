# Worker flow — `worker.handlers.jira_handler.handle_jira_event`

- Module: `worker.handlers.jira_handler`
- Source: [worker.handlers.jira_handler.handle_jira_event](../Src/backend/worker/handlers/jira_handler.py#L11)

```mermaid
sequenceDiagram
    autonumber
    participant Caller
    participant Target as handle_jira_event
    Target->>Dependency: logger.info
    Target->>Dependency: processor.process
    Target->>Dependency: worker.services.jira_processor.JiraEventProcessor
    Target-->>Caller: result
    alt Error path
        Target-->>Caller: raises exception / records triage
    end
```