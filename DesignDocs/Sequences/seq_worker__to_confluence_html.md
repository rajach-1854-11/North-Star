# Sequence: Worker to_confluence_html

**Source:** [`evidence_builder.py`](../../Src/backend/worker/handlers/evidence_builder.py#L51)

```mermaid
sequenceDiagram
    autonumber
    participant Scheduler as RQ Scheduler
    participant Worker as to_confluence_html
    participant Evidence as evidence.replace.replace.replace
    participant Ln as ln.strip
    participant Esc as esc.split
    participant Join as join
    Scheduler->>Worker: Invoke handler
    Worker->>Evidence: evidence.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    Worker->>Evidence: evidence.replace('&', '&amp;').replace('<', '&lt;')
    Worker->>Evidence: evidence.replace('&', '&amp;')
    Worker->>Ln: ln.strip()
    Worker->>Esc: esc.split('\n')
    Worker->>Ln: ln.strip()
    Worker->>Join: ''.join((f'<p>{line}</p>' for line in lines))
```
