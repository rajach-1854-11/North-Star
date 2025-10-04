# Sequence: Job enqueue_jira_event

**Source:** [`job_queue.py`](../../Src/backend/worker/job_queue.py#L47)

```mermaid
sequenceDiagram
    autonumber
    participant API as enqueue_jira_event
    participant Queue as Queue
    API->>Queue: Enqueue job
    API->>Queue: queue.enqueue(handle_jira_event, payload, job_timeout=300)
```
